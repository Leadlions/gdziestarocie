import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    publishedAt: z.coerce.date(),
    updatedAt: z.coerce.date().optional(),
    tags: z.array(z.string()).optional(),
    author: z.string().default('Redakcja gdziestarocie.pl'),
  }),
});

const regiony = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    regionName: z.string(),
    publishedAt: z.coerce.date(),
    updatedAt: z.coerce.date().optional(),
    keywords: z.array(z.string()).optional(),
  }),
});

export const collections = { blog, regiony };
