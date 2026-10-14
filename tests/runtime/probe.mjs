// Diagnostic only. No telemetry, storage, remote fonts, or third-party requests.
export async function digest(value) {
  const bytes = value instanceof Uint8Array ? value : new TextEncoder().encode(JSON.stringify(value));
  if (!globalThis.crypto?.subtle) return { unavailable: 'SHA-256 requires a secure context' };
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
    .map(b => b.toString(16).padStart(2, '0')).join('');
}
const blobHash = async blob => digest(new Uint8Array(await blob.arrayBuffer()));
function draw(canvas) {
  canvas.width = 240; canvas.height = 80;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#f6d'; ctx.fillRect(0, 0, 240, 80);
  ctx.font = '18px sans-serif'; ctx.fillStyle = '#183';
  ctx.fillText('Tor privacy test Ω 한글', 4, 28);
  ctx.globalCompositeOperation = 'multiply';
  ctx.fillStyle = '#ac8'; ctx.beginPath(); ctx.arc(75, 40, 25, 0, 7); ctx.fill();
  return ctx;
}
async function safe(fn) {
  try { return await fn(); } catch (e) { return { unavailable: e.name }; }
}
export async function canvasSample() {
  const canvas = document.createElement('canvas');
  const ctx = draw(canvas);
  const image = () => digest(new Uint8Array(ctx.getImageData(0, 0, 240, 80).data.buffer));
  return {
    getImageData: [await safe(image), await safe(image)],
    textMetrics: ctx.measureText('Tor privacy test Ω 한글').width,
    toDataURL: [
      await safe(() => digest(canvas.toDataURL())), await safe(() => digest(canvas.toDataURL()))],
    toBlob: [await safe(() => new Promise(resolve => canvas.toBlob(async b => resolve(b ? await blobHash(b) : null)))),
      await safe(() => new Promise(resolve => canvas.toBlob(async b => resolve(b ? await blobHash(b) : null))))],
  };
}
// Keep async blob conversion outside the rendering operation.
async function offscreenBlob(canvas) { return blobHash(await canvas.convertToBlob()); }

export async function offscreenSample() {
  const canvas = new OffscreenCanvas(240, 80), ctx = draw(canvas);
  return { getImageData: [await digest(new Uint8Array(ctx.getImageData(0, 0, 240, 80).data.buffer)),
    await digest(new Uint8Array(ctx.getImageData(0, 0, 240, 80).data.buffer))],
    convertToBlob: [await offscreenBlob(canvas), await offscreenBlob(canvas)],
    textMetrics: ctx.measureText('Tor privacy test Ω 한글').width };
}
export async function webglSample(version) {
  const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 64;
  const gl = canvas.getContext(version === 2 ? 'webgl2' : 'webgl');
  if (!gl) return { unavailable: 'context disabled or unsupported' };
  try {
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    const report = {
      vendor: gl.getParameter(gl.VENDOR), renderer: gl.getParameter(gl.RENDERER),
      unmaskedVendor: ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : null,
      unmaskedRenderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null,
      extensions: (gl.getSupportedExtensions() || []).sort(),
      maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
      maxRenderbufferSize: gl.getParameter(gl.MAX_RENDERBUFFER_SIZE),
      maxViewport: Array.from(gl.getParameter(gl.MAX_VIEWPORT_DIMS)),
      shaderPrecision: [gl.VERTEX_SHADER, gl.FRAGMENT_SHADER].map(type => {
        const p = gl.getShaderPrecisionFormat(type, gl.HIGH_FLOAT);
        return p && [p.rangeMin, p.rangeMax, p.precision];
      }),
    };
    // Render a shader, not just a blank/constant canvas. This is one sample,
    // not exhaustive coverage of all shaders or pixel formats.
    const program = gl.createProgram();
    for (const [type, source] of [
      [gl.VERTEX_SHADER, 'attribute vec2 p; void main(){gl_Position=vec4(p,0.,1.);}'],
      [gl.FRAGMENT_SHADER, 'precision mediump float; void main(){gl_FragColor=vec4(sin(gl_FragCoord.x*.13)*.5+.5,gl_FragCoord.y/64.,.3,1.);}'],
    ]) {
      const shader = gl.createShader(type); gl.shaderSource(shader, source); gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw Error('Shader compilation failed');
      gl.attachShader(program, shader); gl.deleteShader(shader);
    }
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error('Shader link failed');
    gl.useProgram(program);
    const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,3,-1,-1,3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(program, 'p'); gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0); gl.drawArrays(gl.TRIANGLES, 0, 3);
    const read = async () => { const pixels = new Uint8Array(64*64*4);
      gl.readPixels(0, 0, 64, 64, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      if (gl.getError() !== gl.NO_ERROR) throw Error('readPixels failed');
      return digest(pixels); };
    const result = { report, reportHash: await digest(report), readPixels: [await read(), await read()],
      toDataURL: await digest(canvas.toDataURL()) };
    if (version === 2) result.pixelPackBuffer = await safe(async () => {
      const b = gl.createBuffer(); gl.bindBuffer(gl.PIXEL_PACK_BUFFER, b);
      gl.bufferData(gl.PIXEL_PACK_BUFFER, 64*64*4, gl.STREAM_READ);
      gl.readPixels(0, 0, 64, 64, gl.RGBA, gl.UNSIGNED_BYTE, 0);
      gl.finish(); const bytes = new Uint8Array(64*64*4);
      gl.getBufferSubData(gl.PIXEL_PACK_BUFFER, 0, bytes);
      if (gl.getError() !== gl.NO_ERROR) throw Error('PBO extraction failed');
      gl.deleteBuffer(b); return digest(bytes);
    });
    return result;
  } finally { gl.getExtension('WEBGL_lose_context')?.loseContext(); }
}
export function identity() {
  return Object.fromEntries(['userAgent', 'platform', 'oscpu', 'appVersion', 'maxTouchPoints',
    'hardwareConcurrency', 'language', 'languages', 'deviceMemory'].map(k => [k, navigator[k] ?? null]));
}
export async function probe() {
  const queries = ['(pointer: coarse)', '(pointer: fine)', '(hover: hover)', '(any-pointer: coarse)',
    '(prefers-color-scheme: dark)', '(prefers-reduced-motion: reduce)', '(orientation: portrait)'];
  const audio = await safe(async () => {
    const ctx = new OfflineAudioContext(1, 4410, 44100), oscillator = ctx.createOscillator();
    const compressor = ctx.createDynamicsCompressor(); oscillator.type = 'triangle'; oscillator.frequency.value = 1000;
    oscillator.connect(compressor); compressor.connect(ctx.destination); oscillator.start(0);
    const b = await ctx.startRendering(); return { sampleRate: b.sampleRate,
      hash: await digest(new Uint8Array(b.getChannelData(0).buffer)) };
  });
  const fontContext = document.createElement('canvas').getContext('2d');
  const fonts = Object.fromEntries(['sans-serif','serif','monospace','Arial','Times New Roman',
    'Helvetica','Apple Color Emoji','-apple-system'].map(font => {
      fontContext.font = `18px "${font}", monospace`;
      return [font,fontContext.measureText('mmmmiiii Ω 한글 😀').width];
    }));
  return { identity: identity(), fontMetrics: fonts,
    fontNote: 'Widths alone do not prove a font is installed; compare fallback/control devices.',
    clientHints: await safe(async () => navigator.userAgentData ?
    await navigator.userAgentData.getHighEntropyValues(['platform','architecture','model']) : null),
    screen: [screen.width, screen.height, screen.availWidth, screen.availHeight, screen.colorDepth],
    viewport: [innerWidth, innerHeight, outerWidth, outerHeight, devicePixelRatio,
      visualViewport?.width, visualViewport?.height, visualViewport?.scale],
    css: Object.fromEntries(queries.map(q => [q, matchMedia(q).matches])),
    timezone: Intl.DateTimeFormat().resolvedOptions(), offsetMinutes: new Date().getTimezoneOffset(),
    api: { webgpu: 'gpu' in navigator, webRTC: typeof RTCPeerConnection !== 'undefined',
      touchEvents: 'ontouchstart' in globalThis },
    speechVoices: await safe(() => speechSynthesis.getVoices().map(v => ({name:v.name,lang:v.lang,local:v.localService}))),
    canvas: await safe(() => canvasSample()), offscreen: await safe(offscreenSample),
    webgl1: await safe(() => webglSample(1)), webgl2: await safe(() => webglSample(2)), audio };
}
