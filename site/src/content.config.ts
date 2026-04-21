import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const editions = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "src/content/editions" }),
  schema: z.object({
    month: z.string(),
    publication_date: z
      .union([z.string(), z.date()])
      .transform((v) => (typeof v === 'string' ? v : v.toISOString().slice(0, 10))),
  }),
});

export const collections = { editions };
