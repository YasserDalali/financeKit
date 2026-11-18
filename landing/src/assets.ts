/**
 * Preloads everything the page needs and reports real progress (0–1) while doing it.
 * Videos are downloaded into memory (streamed, so progress is byte-accurate) and served to the page as blob URLs;
 * that also makes scrubbing instant and independent of range-request support. `src()` returns the blob URL when there is one.
 */

type Job = { url: string; kind: 'video' | 'image' | 'font'; weight: number };

const isPhone = () => matchMedia('(max-width: 767px)').matches;

const jobs = (): Job[] => {
  const list: Job[] = [
    { url: '/assets/hero-loop.mp4', kind: 'video', weight: 8 },
    { url: '/assets/hero-poster.jpg', kind: 'image', weight: 1 },
    { url: '/assets/wave.jpg', kind: 'image', weight: 1 },
    ...[1, 2, 3, 4].map((n) => ({ url: `/assets/icon-${n}.png`, kind: 'image' as const, weight: 0.5 })),
    ...['portfolio', 'fundamentals', 'valuation', 'stress', 'tower'].map((n) => ({ url: `/assets/card-${n}.webp`, kind: 'image' as const, weight: 0.5 })),
    { url: 'fonts', kind: 'font', weight: 1 },
  ];
  // Phones get the still helix image instead of the scrubbed clip, so skip the big download
  if (isPhone()) list.push({ url: '/assets/ribbon.jpg', kind: 'image', weight: 1 });
  else list.push({ url: '/assets/helix-scrub.mp4', kind: 'video', weight: 14 }, { url: '/assets/helix-poster.jpg', kind: 'image', weight: 1 });
  return list;
};

const blobs = new Map<string, string>();
/** Preloaded blob URL for a path, or the path itself if it wasn't preloaded. */
export const src = (path: string) => blobs.get(path) ?? path;

async function loadVideo(url: string, onFrac: (f: number) => void) {
  const res = await fetch(url);
  const total = Number(res.headers.get('content-length')) || 0;
  const reader = res.body?.getReader();
  if (!reader) { blobs.set(url, URL.createObjectURL(await res.blob())); return; }
  const chunks: Uint8Array<ArrayBuffer>[] = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value as Uint8Array<ArrayBuffer>);
    got += value.length;
    if (total) onFrac(Math.min(0.99, got / total));
  }
  blobs.set(url, URL.createObjectURL(new Blob(chunks, { type: res.headers.get('content-type') ?? 'video/mp4' })));
}

async function loadImage(url: string) {
  const img = new Image();
  img.src = url;
  await img.decode();
}

async function loadFonts() {
  await Promise.all([
    document.fonts.load('italic 1em "Instrument Serif"'),
    document.fonts.load('400 1em "Instrument Serif"'),
    document.fonts.load('500 1em "Hanken Grotesk"'),
    document.fonts.load('600 1em "Hanken Grotesk"'),
  ]);
  await document.fonts.ready;
}

/** Resolves when everything is loaded (or failed — a missing asset must never trap the user on the intro). */
export function preload(onProgress: (p: number) => void): Promise<void> {
  const list = jobs();
  const frac = list.map(() => 0);
  const totalWeight = list.reduce((s, j) => s + j.weight, 0);
  const report = () => onProgress(list.reduce((s, j, i) => s + j.weight * frac[i], 0) / totalWeight);

  const runs = list.map((job, i) => {
    const set = (f: number) => { frac[i] = f; report(); };
    const work = job.kind === 'video' ? loadVideo(job.url, set) : job.kind === 'image' ? loadImage(job.url) : loadFonts();
    return work.catch(() => {}).then(() => set(1));
  });
  const timeout = new Promise<void>((r) => setTimeout(r, 20000)); // safety net
  return Promise.race([Promise.all(runs).then(() => {}), timeout]).then(() => onProgress(1));
}
