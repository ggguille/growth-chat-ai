import { test, expect, type Page } from '@playwright/test';
import { collectSseEvents } from './helpers/sse';

const STAGING_API_URL = process.env.VITE_API_URL!;
const FALLBACK_URL = process.env.VITE_FALLBACK_URL ?? 'https://example.com/contact';

function testPageUrl() {
  const params = new URLSearchParams({
    'api-url': STAGING_API_URL,
    'fallback-url': FALLBACK_URL,
  });
  return `/test-page.html?${params.toString()}`;
}

// Helpers to locate elements inside the Shadow DOM.
// Playwright's chained .locator() automatically pierces shadow roots.
const w = (page: Page) => page.locator('growth-chat');
const launcher      = (page: Page) => w(page).locator('[data-testid="launcher-button"]');
const gdprAccept    = (page: Page) => w(page).locator('[data-testid="gdpr-accept"]');
const messageInput  = (page: Page) => w(page).locator('[data-testid="message-input"]');
const messageList   = (page: Page) => w(page).locator('[data-testid="message-list"]');
const fallbackBanner = (page: Page) => w(page).locator('[data-testid="fallback-banner"]');
const fallbackLink  = (page: Page) => w(page).locator('[data-testid="fallback-link"]');
const errorMessage  = (page: Page) => w(page).locator('[data-testid="error-message"]');

test.beforeEach(async ({ page }) => {
  await page.goto(testPageUrl());
});

// ─── E2E-01: Widget loads and launcher renders ───────────────────────────────

test('E2E-01: widget launcher renders within Shadow DOM', async ({ page }) => {
  await expect(launcher(page)).toBeVisible({ timeout: 5_000 });

  // proactive-delay-ms is set to 2000ms on the test page; wait up to 5s for the bubble
  const proactivePrompt = page.locator('growth-chat').locator('[data-testid="proactive-prompt"]');
  await expect(proactivePrompt).toBeVisible({ timeout: 5_000 });
});

// ─── E2E-02: Message sends and streaming response renders ────────────────────

test('E2E-02: message sends and streaming response renders', async ({ page }) => {
  // Set up response capture before sending the message
  const responsePromise = page.waitForResponse(
    r => r.url().includes('/chat') && r.status() === 200
  );

  await launcher(page).click();
  await gdprAccept(page).click();

  const input = messageInput(page);
  await input.fill('Hi, I have a question about AI engineering for our team.');
  await input.press('Enter');

  // Wait for the response to arrive and collect SSE events
  const response = await responsePromise;
  const bodyText = await response.text();
  const events = await collectSseEvents(bodyText);

  // Assert at least one token appeared in the message list before completion
  await expect(messageList(page)).not.toBeEmpty({ timeout: 10_000 });

  // Input re-enabled signals the done event was received
  await expect(input).toBeEnabled({ timeout: 30_000 });

  expect(events.some(e => e.type === 'error')).toBe(false);
  expect(events.some(e => e.type === 'done')).toBe(true);
});

// ─── E2E-03: Backend unavailable activates fallback state ───────────────────

test('E2E-03: backend 503 activates fallback state', async ({ page }) => {
  await page.route(`${STAGING_API_URL}**`, route =>
    route.fulfill({ status: 503, body: 'Service Unavailable' })
  );

  await launcher(page).click();
  await gdprAccept(page).click();

  const input = messageInput(page);
  await input.fill('Hello');
  await input.press('Enter');

  await expect(fallbackBanner(page)).toBeVisible({ timeout: 10_000 });
  await expect(fallbackLink(page)).toBeVisible();
  await expect(fallbackLink(page)).toHaveAttribute('href', /contact/);
  await expect(input).not.toBeVisible();
});

// ─── E2E-04: Rate limit response displays appropriate message ────────────────

test('E2E-04: rate limit 429 displays user-facing message', async ({ page }) => {
  await page.route(`${STAGING_API_URL}**`, route =>
    route.fulfill({
      status: 429,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'RATE_LIMIT_EXCEEDED',
          message: 'Too many messages. Please wait before sending another.',
          retry_after_seconds: 30,
        },
      }),
    })
  );

  await launcher(page).click();
  await gdprAccept(page).click();

  const input = messageInput(page);
  await input.fill('Hello');
  await input.press('Enter');

  await expect(errorMessage(page)).toContainText(/too many/i, { timeout: 5_000 });

  // Input re-enabled — rate limit is a turn-level error, not a permanent failure
  await expect(input).toBeEnabled({ timeout: 5_000 });

  // Fallback banner must NOT appear — 429 is not a service unavailability signal
  await expect(fallbackBanner(page)).not.toBeVisible();
});

// ─── E2E-05: Multi-turn hot lead conversation reaches Stage 3 proposal ───────

test('E2E-05: hot lead conversation triggers Stage 3 proposal', async ({ page }) => {
  await launcher(page).click();
  await gdprAccept(page).click();

  const input = messageInput(page);

  // Turn 1 — establish context
  await input.fill(
    "Hi, I'm the CTO at a fintech scale-up and we're evaluating AI engineering partners for a RAG-based internal knowledge system. We need to make a decision by end of Q3."
  );
  await input.press('Enter');
  await expect(input).toBeEnabled({ timeout: 30_000 });

  // Set up capture for turn 2 response before sending the second message
  const turn2ResponsePromise = page.waitForResponse(
    r => r.url().includes('/chat') && r.status() === 200
  );

  // Turn 2 — confirm hot lead signals
  await input.fill(
    'We have a team of 5 engineers but no ML expertise. Budget is confirmed. We need an external partner to lead the build.'
  );
  await input.press('Enter');

  const turn2Response = await turn2ResponsePromise;
  const turn2Body = await turn2Response.text();
  const turn2Events = await collectSseEvents(turn2Body);

  await expect(input).toBeEnabled({ timeout: 30_000 });

  // Assert done event signals Stage 3 proposal was issued
  const doneEvent = turn2Events.find(e => e.type === 'done');
  expect(doneEvent).toBeDefined();
  expect(doneEvent?.stage3_proposal_issued).toBe(true);

  // Assert proposal text is visible in the message list
  await expect(messageList(page)).toContainText(/email|connect|follow.?up/i);
}, { timeout: 60_000 });
