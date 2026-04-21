import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';

export default defineConfig({
  site: 'https://iris.cefic.org',
  integrations: [mdx()],
});
