import {identity, offscreenSample} from './probe.mjs';
let offscreen;
try { offscreen = await offscreenSample(); } catch(e) { offscreen = {unavailable:e.name}; }
postMessage({identity:identity(), timezone:Intl.DateTimeFormat().resolvedOptions(), offscreen});
