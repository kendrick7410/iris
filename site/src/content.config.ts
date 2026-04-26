import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const editions = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "src/content/editions" }),
  schema: z.object({
    month: z.string(),
    publication_date: z
      .union([z.string(), z.date()])
      .transform((v) => (typeof v === 'string' ? v : v.toISOString().slice(0, 10))),
    // Marks an edition as human-reviewed (Moncef). Once true, the pipeline
    // must not regenerate the MDX without --force. See STATE.md §9.
    reviewed: z.boolean().optional().default(false),
    pipeline_version: z.string().optional(),
    // Editorial validator output. Surfaced in the Sveltia CMS so Moncef
    // sees per-section flags above the body. Never rendered on the public
    // site — lives in entry.data only and is filtered out of templates.
    validation: z
      .object({
        generated_at: z
          .union([z.string(), z.date()])
          .transform((v) => (typeof v === 'string' ? v : v.toISOString())),
        summary: z
          .object({
            critical: z.number(),
            warning: z.number(),
            info: z.number(),
            sections_validated: z.number(),
          })
          .optional(),
        flags: z
          .array(
            z.object({
              section: z.string(),
              severity: z.enum(['critical', 'warning', 'info']),
              flag_id: z.string(),
              message: z.string(),
              citation: z.string().optional(),
              pattern_ref: z.string().optional(),
              suggested_resolution: z.string().optional(),
            }),
          )
          .default([]),
      })
      .optional(),
  }),
});

export const collections = { editions };
