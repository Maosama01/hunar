// Client-side photo handling: downscale to at most 1280 px JPEG before queueing, so uploads stay
// small on slow connections. Faces are blurred by the server before anything is stored there.

export const MAX_DIM = 1280;
export const JPEG_QUALITY = 0.85;
const THUMB_DIM = 320;

export interface PreparedPhoto {
  /** Base64 JPEG without the data: prefix, as evidence.add expects in image_b64. */
  b64: string;
  /** Small local preview (data URL). */
  thumb: string;
  width: number;
  height: number;
  bytes: number;
}

interface Decoded {
  source: CanvasImageSource;
  width: number;
  height: number;
  close: () => void;
}

async function decode(blob: Blob): Promise<Decoded> {
  if (typeof createImageBitmap === "function") {
    try {
      // Applies the EXIF orientation of phone photos.
      const bmp = await createImageBitmap(blob, { imageOrientation: "from-image" } as ImageBitmapOptions);
      return { source: bmp, width: bmp.width, height: bmp.height, close: () => bmp.close() };
    } catch {
      /* fall back to an <img> element */
    }
  }
  const url = URL.createObjectURL(blob);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return { source: img, width: img.naturalWidth, height: img.naturalHeight, close: () => URL.revokeObjectURL(url) };
  } catch (e) {
    URL.revokeObjectURL(url);
    throw new Error("this file is not an image the browser can read");
  }
}

function drawScaled(d: Decoded, maxDim: number): HTMLCanvasElement {
  const scale = Math.min(1, maxDim / Math.max(d.width, d.height));
  const w = Math.max(1, Math.round(d.width * scale));
  const h = Math.max(1, Math.round(d.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas is not available");
  ctx.fillStyle = "#fff"; // JPEG has no alpha
  ctx.fillRect(0, 0, w, h);
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(d.source, 0, 0, w, h);
  return canvas;
}

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("could not encode JPEG"))), "image/jpeg", quality),
  );
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error ?? new Error("could not read the image"));
    r.readAsDataURL(blob);
  });
}

export async function preparePhoto(file: Blob, maxDim = MAX_DIM, quality = JPEG_QUALITY): Promise<PreparedPhoto> {
  const d = await decode(file);
  try {
    const big = drawScaled(d, maxDim);
    const blob = await toBlob(big, quality);
    const dataUrl = await blobToDataUrl(blob);
    const thumb = drawScaled(d, THUMB_DIM).toDataURL("image/jpeg", 0.7);
    return { b64: dataUrl.slice(dataUrl.indexOf(",") + 1), thumb, width: big.width, height: big.height, bytes: blob.size };
  } finally {
    d.close();
  }
}

/** Thumbnail of an image on the server (the face-blurred copy), for offline display. */
export async function thumbFromUrl(url: string): Promise<string | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const d = await decode(await res.blob());
    try {
      return drawScaled(d, THUMB_DIM).toDataURL("image/jpeg", 0.7);
    } finally {
      d.close();
    }
  } catch {
    return null;
  }
}
