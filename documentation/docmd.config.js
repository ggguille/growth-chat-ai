// docmd.config.js
export default defineConfig({
  // --- Core Metadata ---
  title: 'Growth Chat Documentation',
  url: 'https://growth-chat-ai.ggguille.com', // e.g. https://mysite.com (Critical for SEO/Sitemap)

  // --- Branding ---
  logo: {
    light: 'assets/images/docmd-logo-dark.png',
    dark: 'assets/images/docmd-logo-light.png',
    alt: 'Logo',
    href: '/',
  },
  favicon: 'assets/favicon.ico',

  // --- Source & Output ---
  src: 'docs',
  out: 'site',

  // --- Layout & UI Architecture ---
  layout: {
    spa: true, // Enable seamless page transitions
    header: {
      enabled: true,
    },
    sidebar: {
      collapsible: true,
      defaultCollapsed: false,
    },
    optionsMenu: {
      position: 'sidebar-top', // 'menubar', 'header', 'sidebar-top', 'sidebar-bottom'
      components: {
        search: true,      
        themeSwitch: true, 
        sponsor: null,     
      }
    },
    footer: {
      style: 'minimal', // 'minimal' or 'complete'
      content: '© ' + new Date().getFullYear() + ' My Project.',
      branding: true    // Config for "Built with docmd" badge
    }
  },

  // --- Theme Settings ---
  theme: {
    name: 'default',        // Options: 'default', 'sky', 'ruby', 'retro'
    appearance: 'system',   // 'light', 'dark', or 'system'
    codeHighlight: true,    
    customCss: [],          
  },

  // --- General Features ---
  minify: true,           
  autoTitleFromH1: true,  
  copyCode: true,         
  pageNavigation: true,   
  
  customJs: [],           

  // --- Versioning (Optional) ---
  /*
  versions: {
    position: 'sidebar-top', // 'sidebar-top', 'sidebar-bottom'
    current: 'v2',
    all: [
      { id: 'v2',       // Unique identifier for this version (used in URLs) and matching current version
       dir: 'docs',     // Source directory for latest version
       label: 'v2.0 (Latest)'
      },
      { id: 'v1',
       dir: 'docs-v1',  // Source directory for older version
       label: 'v1.0'
      }
    ]
  },
  */

  // --- Navigation (Sidebar) ---
  navigation: [
    { title: 'Introduction', path: '/', icon: 'home' },
    { title: 'Discovery Artifact', path: '/discovery-artifact', icon: 'rocket' },
    { title: 'Problem Statement', path: '/problem-statement', icon: 'clipboard' },
    {
      title: 'Product Requirements',
      path: '/product-requirements',
      icon: 'file-text',
      children: [
        { title: 'Engineering Review', path: '/product-requirements/engineering-review' },
        { title: 'Stakeholder Review', path: '/product-requirements/stakeholder-review' },
      ]
    },
    {
      title: 'Considerations',
      path: '/considerations',
      icon: 'lightbulb',
      children: [
        { title: 'Chat Behaviour', path: '/considerations/chat-behaviour' },
        { title: 'Qualification Signals', path: '/considerations/qualification-signals' },
        { title: 'Human Handoff', path: '/considerations/human-handoff' },
      ]
    },
    {
      title: 'User Personas',
      path: '/user-personas',
      icon: 'users',
      children: [
        { title: 'P1 — Evaluating CTO', path: '/user-personas/p1-evaluating-cto' },
        { title: 'P2 — Exploring Founder', path: '/user-personas/p2-exploring-founder' },
        { title: 'P3 — Referred Decision-Maker', path: '/user-personas/p3-referred-decision-maker' },
        { title: 'N1 — Competitor', path: '/user-personas/n1-competitor' },
        { title: 'N2 — Curious Researcher', path: '/user-personas/n2-curious-researcher' },
      ]
    },
  ],

  // --- Plugins ---
  plugins: {
    seo: {
      defaultDescription: 'Documentation built with docmd.',
      openGraph: { defaultImage: '' },
      twitter: { cardType: 'summary_large_image' }
    },
    sitemap: { defaultChangefreq: 'weekly' },
    analytics: { 
      googleV4: { measurementId: 'G-X9WTDL262N' } // Change the example GA ID with your own
    }
  },
  
  // --- Edit Link ---
  editLink: {
    enabled: false,
    baseUrl: 'https://github.com/USERNAME/REPO/edit/main/docs',
    text: 'Edit this page'
  }
});
