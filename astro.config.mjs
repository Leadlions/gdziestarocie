import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import mdx from '@astrojs/mdx';

// @astrojs/sitemap can be re-enabled after deploying to production
// (requires a compatible version for Astro 4.16)
export default defineConfig({
  site: 'https://gdziestarocie.pl',
  integrations: [tailwind(), mdx()],
});
