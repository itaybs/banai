// Straight-on front view of the wardrobe for the design summary PDF (an illustrative image).
// Pure framing math here; viewer.captureFront() does the rendering.

export const CAPTURE_WIDTH = 900;
export const CAPTURE_HEIGHT = 1000;
const MARGIN = 1.12; // a little room around the wardrobe

/**
 * Camera position and target (metres) that fit the whole front of the wardrobe in a frame of the
 * given aspect ratio, looking straight at it. Dimensions are millimetres, as in the design.
 */
export function frontView({ width, height, depth }, fovDegrees, aspect) {
  const w = width / 1000;
  const h = height / 1000;
  const d = depth / 1000;
  const vertical = (fovDegrees * Math.PI) / 180;
  const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * aspect);
  const fitHeight = (h / 2) / Math.tan(vertical / 2);
  const fitWidth = (w / 2) / Math.tan(horizontal / 2);
  const distance = Math.max(fitHeight, fitWidth) * MARGIN;
  const target = { x: w / 2, y: h / 2, z: -d / 2 };
  return { target, position: { x: target.x, y: target.y, z: distance } }; // the front face is at z = 0
}
