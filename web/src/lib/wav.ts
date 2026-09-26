/* Запись микрофона → WAV 16 кГц моно (16 бит). Браузеры пишут кто WebM/Opus (Chrome),
   кто MP4/AAC (Safari) — переводим в WAV, который модель точно поймёт. ~32 КБ на секунду. */

const RATE = 16000;

function writeString(view: DataView, offset: number, text: string) {
  for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
}

export async function toWav(recorded: Blob): Promise<Blob> {
  const ctx = new AudioContext();
  let decoded: AudioBuffer;
  try {
    decoded = await ctx.decodeAudioData(await recorded.arrayBuffer());
  } finally {
    void ctx.close();
  }
  const length = Math.max(1, Math.ceil(decoded.duration * RATE));
  const offline = new OfflineAudioContext(1, length, RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const samples = (await offline.startRendering()).getChannelData(0);

  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true); // размер блока fmt
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // моно
  view.setUint32(24, RATE, true);
  view.setUint32(28, RATE * 2, true); // байт в секунду
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}
