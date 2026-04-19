// docmd.config.js
export default defineConfig({
  // --- Core Metadata ---
  title: 'My Documentation',
  url: '', // e.g. https://mysite.com (Critical for SEO/Sitemap)

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
