import type { Philosopher } from '@/types';
import { socrates } from './socrates';
import { nietzsche } from './nietzsche';
import { beauvoir } from './beauvoir';

export const philosophers: Record<string, Philosopher> = { socrates, nietzsche, beauvoir };
export const philosopherList = Object.values(philosophers);
export const getPhilosopher = (id: string) => philosophers[id];
