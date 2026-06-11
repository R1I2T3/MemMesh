import { z } from 'zod';

export const evalSearchSchema = z.object({
  days: z.coerce.number().min(1).max(365).optional().default(30),
});

export const chatSearchSchema = z.object({
  session: z.string().optional(),
});
