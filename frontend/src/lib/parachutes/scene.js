// Cards parachuting onto a kanban board: the pearachute mark, played out.
//
// A three.js scene with no Svelte in it, so it can be imported lazily (three
// is a few hundred KB, and only pages that show the scene should pay for it)
// and so the choreography reads top to bottom in one file. The component that
// mounts it is components/ParachuteScene.svelte.
//
// The story loops without a seam: a card drifts down under a pear-canopy
// parachute into Todo, its chute lifts away, and cards work their way across
// to Done, where the oldest eventually sinks out to make room.

import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// --- Layout (world units; the board is ~10 wide, lying on y = 0) -------------

const COLUMNS = ['Todo', 'In Progress', 'Done'];
const COLUMN_X = [-3.35, 0, 3.35];
const COLUMN_W = 3.0;
const CARD_W = 2.6;
const CARD_H = 0.12;
const CARD_D = 1.05;
const ROW_GAP = 1.3;
const FIRST_ROW_Z = -1.75;
const MAX_IN_DONE = 4;

// --- Timing (seconds) ---------------------------------------------------------

// Everything below runs at this fraction of real time: the board, the
// chutes and the camera alike. 0.8 = a fifth slower than the numbers say.
const TIME_SCALE = 0.8;

const TICK = 2.3; // one board event this often
const DROP = 3.4; // parachute descent
const LIFT_OFF = 1.6; // chute leaving after landing
const MOVE = 1.25; // card crossing to the next column
const SINK = 1.2; // oldest Done card leaving
const INTRO = 5; // opening camera move
const LAND = 0.42; // the squash as a card touches down
const RING = 0.75; // the ring spreading out under it

// Depth of field, focused on the middle of the board. Blur grows with
// distance from the focal plane at APERTURE per world unit, up to MAX_BLUR
// (a fraction of the frame). Off below DOF_MIN_WIDTH pixels, where it costs
// the GPU more than it shows.
const APERTURE = 0.0024;
const MAX_BLUR = 0.01;
const DOF_MIN_WIDTH = 560;
const FOCUS_PULL = 2.2; // how fast focus racks to a new subject (per second)

// A chute drifting down right past the lens now and then: big, out of focus,
// and the clearest thing in the frame about how deep the shot is.
const FLYBY_EVERY = 18;
const FLYBY = 6;

const DROP_HEIGHT = 7.5;
const CANOPY_Y = 2.35; // canopy above its card
const CANOPY_R = 1.2;

// Card titles: the kind of work that lands on a board like this one.
const TITLES = [
  'Fix API latency',
  'Add card search',
  'Card archiving',
  'Publish a DMARC record',
  'Paginate card lists',
  'Rate-limit API keys',
  'Markdown in card bodies',
  'MCP connector for Claude',
  'Bulk import from a file',
  'Board header on phones',
  'Flaky admin test',
  'Scope API keys per board',
];

const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeInQuad = (t) => t * t;
const clamp01 = (t) => Math.min(1, Math.max(0, t));

/**
 * Build the scene on `canvas`.
 *
 * palette: { background, surface, card, ink, muted, primary, accent, border },
 *   CSS color strings (ParachuteScene resolves them from the theme tokens).
 * reducedMotion: draw one composed still and never animate.
 *
 * Returns { resize(w, h), setPalette(p), setPointer(x, y), play(), pause(), dispose() }.
 */
export function createParachuteScene(canvas, { palette, reducedMotion = false }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const maxAniso = renderer.capabilities.getMaxAnisotropy();

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);

  // Multisampled buffers: the composer renders off screen, where the
  // renderer's own antialiasing does not reach, and the 1px cords stair-stepped.
  const composer = new EffectComposer(
    renderer,
    new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 }),
  );
  composer.addPass(new RenderPass(scene, camera));
  const bokeh = new BokehPass(scene, camera, { focus: 11, aperture: APERTURE, maxblur: MAX_BLUR });
  composer.addPass(bokeh);
  composer.addPass(new OutputPass());
  let dof = true;

  // Everything disposable, so dispose() can let go of the GPU memory.
  const owned = new Set();
  const own = (thing) => (owned.add(thing), thing);

  // --- Colors ----------------------------------------------------------------

  const colors = {};
  function applyPalette(p) {
    for (const [key, value] of Object.entries(p)) colors[key] = new THREE.Color(value);
    colors.canopyLight = colors.primary.clone().lerp(new THREE.Color('#ffffff'), 0.72);
    // Light themes want a brighter sky; read it off the background itself.
    colors.isLight = colors.background.getHSL({}).l > 0.5;
  }
  applyPalette(palette);

  // --- Lighting & atmosphere ---------------------------------------------------

  const hemi = new THREE.HemisphereLight(0xffffff, 0x000000, 0.9);
  scene.add(hemi);

  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(4.5, 11, 5.5);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -9;
  key.shadow.camera.right = 9;
  key.shadow.camera.top = 9;
  key.shadow.camera.bottom = -9;
  key.shadow.camera.far = 40;
  key.shadow.radius = 6;
  key.shadow.bias = -0.0004;
  scene.add(key);

  // A cool light from behind the board, to edge the canopies.
  const rim = new THREE.DirectionalLight(0xffffff, 0.7);
  rim.position.set(-6, 5, -9);
  scene.add(rim);

  scene.fog = new THREE.Fog(0x000000, 13, 30);

  // --- The board ---------------------------------------------------------------

  // The floor draws only the shadows that fall on it. A lit floor came out
  // lighter than the page, even in the page's own color, and showed the
  // canvas as a box; this way the scene's ground is the page itself.
  const floorMat = own(new THREE.ShadowMaterial());
  const floor = new THREE.Mesh(own(new THREE.PlaneGeometry(80, 80)), floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -0.06;
  floor.receiveShadow = true;
  scene.add(floor);

  const laneMat = own(new THREE.MeshStandardMaterial({ roughness: 0.85 }));
  const laneGeo = own(new RoundedBoxGeometry(COLUMN_W, 0.06, 6.2, 3, 0.03));
  const headerMeshes = [];
  COLUMNS.forEach((name, i) => {
    const lane = new THREE.Mesh(laneGeo, laneMat);
    lane.position.set(COLUMN_X[i], -0.03, FIRST_ROW_Z + 1.55);
    lane.receiveShadow = true;
    scene.add(lane);

    const header = new THREE.Mesh(own(new THREE.PlaneGeometry(COLUMN_W * 0.9, 0.42)), null);
    header.rotation.x = -Math.PI / 2;
    header.position.set(COLUMN_X[i], 0.005, FIRST_ROW_Z - 0.95);
    header.userData.column = i;
    headerMeshes.push(header);
    scene.add(header);
  });

  function drawHeaders() {
    for (const header of headerMeshes) {
      const i = header.userData.column;
      const c = document.createElement('canvas');
      c.width = 512;
      c.height = 72;
      const g = c.getContext('2d');
      const dot = [colors.muted, colors.primary, colors.accent][i];
      g.fillStyle = `#${dot.getHexString()}`;
      g.beginPath();
      g.arc(22, 36, 10, 0, Math.PI * 2);
      g.fill();
      g.fillStyle = `#${colors.muted.getHexString()}`;
      g.font = '700 34px Ubuntu, "Segoe UI", sans-serif';
      g.letterSpacing = '4px';
      g.textBaseline = 'middle';
      g.fillText(COLUMNS[i].toUpperCase(), 50, 38);
      const tex = new THREE.CanvasTexture(c);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = maxAniso;
      header.material?.map?.dispose();
      header.material?.dispose();
      header.material = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false });
    }
  }

  // --- Cards ---------------------------------------------------------------------

  const cardGeo = own(new RoundedBoxGeometry(CARD_W, CARD_H, CARD_D, 4, 0.05));
  const faceGeo = own(new THREE.PlaneGeometry(CARD_W * 0.94, CARD_D * 0.9));

  function cardTexture(card) {
    const c = document.createElement('canvas');
    c.width = 640;
    c.height = 256;
    const g = c.getContext('2d');
    const idColor = card.column === 2 ? colors.accent : colors.primary;
    g.fillStyle = `#${idColor.getHexString()}`;
    g.font = '700 40px "Ubuntu Mono", ui-monospace, monospace';
    g.textBaseline = 'top';
    g.fillText(`#${card.id}`, 26, 26);
    if (card.column === 2) g.fillText('✓', 580, 26);
    g.fillStyle = `#${colors.ink.getHexString()}`;
    g.font = '500 54px Ubuntu, "Segoe UI", sans-serif';
    // Two lines at most, broken on words.
    const words = card.title.split(' ');
    const lines = [''];
    for (const word of words) {
      const next = lines[lines.length - 1] ? `${lines[lines.length - 1]} ${word}` : word;
      if (g.measureText(next).width > 588 && lines[lines.length - 1]) {
        if (lines.length === 2) break;
        lines.push(word);
      } else {
        lines[lines.length - 1] = next;
      }
    }
    lines.forEach((line, n) => g.fillText(line, 26, 92 + n * 66));
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = maxAniso;
    return tex;
  }

  function paintCard(card) {
    card.body.material.color.copy(colors.card);
    card.face.material.map?.dispose();
    card.face.material.map = cardTexture(card);
    card.face.material.needsUpdate = true;
  }

  let nextId = 981;
  let nextTitle = 0;
  const cards = [];
  const lanes = [[], [], []];

  function makeCard(column) {
    const group = new THREE.Group();
    // Matte: glossier cards caught the cyan rim light full-face whenever
    // the orbiting camera reached the mirror angle, and turned bright cyan.
    const body = new THREE.Mesh(cardGeo, new THREE.MeshStandardMaterial({ roughness: 0.85, transparent: true }));
    body.castShadow = true;
    body.receiveShadow = true;
    const face = new THREE.Mesh(faceGeo, new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false }));
    face.rotation.x = -Math.PI / 2;
    face.position.y = CARD_H / 2 + 0.002;
    group.add(body, face);
    scene.add(group);
    const card = {
      id: nextId++,
      title: TITLES[nextTitle++ % TITLES.length],
      column,
      group,
      body,
      face,
      move: null, // { from: Vector3, t } while crossing columns
      land: null, // { t } while squashing on touchdown
      drop: null, // { t, drift } while under its parachute
      sink: null, // { t } while leaving Done
      chute: null,
    };
    paintCard(card);
    cards.push(card);
    lanes[column].push(card);
    return card;
  }

  function slotOf(card) {
    const lane = lanes[card.column];
    const index = lane.indexOf(card);
    return new THREE.Vector3(COLUMN_X[card.column], 0, FIRST_ROW_Z + Math.max(0, index) * ROW_GAP);
  }

  // Flatten the slab and its face, leaving the chute (also in the group) alone.
  function squash(card, y, xz) {
    card.body.scale.set(xz, y, xz);
    card.face.scale.set(xz, xz, 1);
    card.face.position.y = (CARD_H / 2) * y + 0.002;
  }

  const ringGeo = own(new THREE.RingGeometry(0.62, 0.7, 72));
  const rings = [];
  function spawnRing(at) {
    const mesh = new THREE.Mesh(
      ringGeo,
      new THREE.MeshBasicMaterial({ color: colors.primary, transparent: true, opacity: 0.45, depthWrite: false }),
    );
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(at.x, 0.01, at.z);
    scene.add(mesh);
    rings.push({ mesh, t: 0 });
  }

  function setOpacity(card, opacity) {
    card.body.material.opacity = opacity;
    card.face.material.opacity = opacity;
  }

  function removeCard(card) {
    scene.remove(card.group);
    card.body.material.dispose();
    card.face.material.map?.dispose();
    card.face.material.dispose();
    cards.splice(cards.indexOf(card), 1);
  }

  // --- Parachutes ------------------------------------------------------------------

  // A scalloped dome like the logo's canopy: twelve panels that puff out
  // between their seams, with a hem that dips at the middle of each panel.
  const LOBES = 12;
  const canopyGeo = own(new THREE.SphereGeometry(CANOPY_R, 144, 28, 0, Math.PI * 2, 0, Math.PI * 0.43));
  {
    const pos = canopyGeo.attributes.position;
    const v = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      const phi = Math.atan2(v.z, v.x);
      const puff = Math.abs(Math.cos((phi * LOBES) / 2));
      const towardHem = 1 - v.y / CANOPY_R;
      v.x *= 1 + 0.07 * puff;
      v.z *= 1 + 0.07 * puff;
      v.y -= towardHem * towardHem * 0.32 * puff;
      pos.setXYZ(i, v.x, v.y, v.z);
    }
    canopyGeo.computeVertexNormals();
  }

  // The panels are drawn per pixel, from the angle around the canopy, not
  // stored per vertex: vertex colors smear each stripe edge across a whole
  // strip of the mesh, which read as blurry and stair-stepped up close. Here
  // the edges stay sharp at any size, and the seams are thin ink lines, like
  // the logo's. The uniforms are shared, so a theme switch repaints every chute.
  const canopyUniforms = {
    canopyA: { value: new THREE.Color() },
    canopyB: { value: new THREE.Color() },
    canopySeam: { value: new THREE.Color() },
  };

  function canopyMaterial() {
    const material = new THREE.MeshStandardMaterial({ roughness: 0.62, side: THREE.DoubleSide, transparent: true });
    material.onBeforeCompile = (shader) => {
      Object.assign(shader.uniforms, canopyUniforms);
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\nvarying vec3 vCanopyPos;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvCanopyPos = position;');
      shader.fragmentShader = shader.fragmentShader
        .replace(
          '#include <common>',
          `#include <common>
          varying vec3 vCanopyPos;
          uniform vec3 canopyA;
          uniform vec3 canopyB;
          uniform vec3 canopySeam;`,
        )
        .replace(
          '#include <color_fragment>',
          `#include <color_fragment>
          // Half a panel of offset: the geometry puffs each panel out at
          // multiples of 30 degrees (cos(6 phi) above), so those are the
          // middles of the arcs, and the seams fall halfway between them.
          float around = (atan(vCanopyPos.z, vCanopyPos.x) + PI) / (2.0 * PI) * ${LOBES}.0 + 0.5;
          diffuseColor.rgb = mix(canopyA, canopyB, mod(floor(around), 2.0));
          float toSeam = min(fract(around), 1.0 - fract(around));
          float aa = fwidth(around);
          float seam = 1.0 - smoothstep(0.035, 0.035 + aa * 1.5, toSeam);
          diffuseColor.rgb = mix(diffuseColor.rgb, canopySeam, seam * 0.8);`,
        );
    };
    material.customProgramCacheKey = () => 'pear-canopy';
    return material;
  }

  function paintCanopy() {
    canopyUniforms.canopyA.value.copy(colors.primary);
    canopyUniforms.canopyB.value.copy(colors.canopyLight);
    canopyUniforms.canopySeam.value.copy(colors.isLight ? colors.ink : colors.primary.clone().multiplyScalar(0.45));
  }

  // The rigging, like the logo's: cords run from the canopy's hem down to
  // the pear, and the pear carries the card. Tied to the card's corners, they
  // were left hanging in mid-air once the chute let go. Six cords, at every
  // other seam, which is where the hem sits highest -- the geometry dips the
  // hem mid-panel and leaves it alone at the seams (angles of 15 + 30k deg).
  const PEAR_SCALE = 0.85;
  const PEAR_Y = CARD_H / 2; // standing on the card
  const PEAR_TOP = PEAR_Y + 0.62 * PEAR_SCALE; // where the stem meets the cords
  const cordGeo = own(new THREE.BufferGeometry());
  {
    const pts = [];
    const hemY = CANOPY_Y + CANOPY_R * Math.cos(Math.PI * 0.43);
    const hemR = CANOPY_R * Math.sin(Math.PI * 0.43) * 0.99;
    for (let k = 0; k < 6; k++) {
      const a = Math.PI / 12 + (k * 2 * Math.PI) / 6;
      pts.push(Math.cos(a) * hemR, hemY, Math.sin(a) * hemR);
      pts.push(0, PEAR_TOP, 0);
    }
    cordGeo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  }

  // The pear that rides each card down, turned on a lathe.
  const pearGeo = own(
    new THREE.LatheGeometry(
      [
        [0, 0], [0.17, 0.02], [0.25, 0.1], [0.26, 0.2], [0.21, 0.3],
        [0.14, 0.38], [0.11, 0.47], [0.09, 0.55], [0.05, 0.61], [0, 0.63],
      ].map(([x, y]) => new THREE.Vector2(x, y)),
      32,
    ),
  );
  pearGeo.computeVertexNormals();
  const stemGeo = own(new THREE.CylinderGeometry(0.015, 0.02, 0.12, 6));
  const leafGeo = own(new THREE.SphereGeometry(0.08, 12, 8));

  function makeChute() {
    const group = new THREE.Group();
    const canopy = new THREE.Mesh(canopyGeo, canopyMaterial());
    canopy.position.y = CANOPY_Y;
    canopy.castShadow = true;
    const cords = new THREE.LineSegments(
      cordGeo,
      new THREE.LineBasicMaterial({ color: colors.ink, transparent: true, opacity: 0.55 }),
    );
    const pear = new THREE.Group();
    const fruit = new THREE.Mesh(pearGeo, new THREE.MeshStandardMaterial({ color: '#bfe47e', roughness: 0.5, transparent: true }));
    fruit.castShadow = true;
    const stem = new THREE.Mesh(stemGeo, new THREE.MeshStandardMaterial({ color: '#231f20', transparent: true }));
    stem.position.y = 0.66;
    const leaf = new THREE.Mesh(leafGeo, new THREE.MeshStandardMaterial({ color: colors.accent, roughness: 0.5, transparent: true }));
    leaf.scale.set(1, 0.35, 0.55);
    leaf.position.set(0.08, 0.64, 0);
    leaf.rotation.z = -0.5;
    pear.add(fruit, stem, leaf);
    pear.position.y = PEAR_Y;
    pear.scale.setScalar(PEAR_SCALE);
    group.add(canopy, cords, pear);
    return { group, canopy, cords, pear, liftT: null };
  }

  function disposeChute(chute) {
    chute.group.removeFromParent();
    chute.group.traverse((o) => o.material?.dispose());
  }

  function chuteOpacity(chute, opacity) {
    chute.group.traverse((o) => {
      if (!o.material) return;
      o.material.opacity = o === chute.cords ? 0.55 * opacity : opacity;
    });
  }

  // --- Fly-bys --------------------------------------------------------------------------

  const flybys = [];
  let sinceFlyby = FLYBY_EVERY * 0.5;
  const toBoard = new THREE.Vector3();
  const side = new THREE.Vector3();

  function spawnFlyby() {
    const chute = makeChute();
    // A few units in front of the lens, off to one side, above the frame.
    toBoard.subVectors(target, camera.position).normalize();
    side.crossVectors(toBoard, camera.up).normalize();
    const lean = Math.random() < 0.5 ? -1 : 1;
    const start = camera.position.clone()
      .addScaledVector(toBoard, 5 + Math.random() * 1.5)
      .addScaledVector(side, lean * (1.4 + Math.random() * 0.8));
    start.y += 2.6;
    chute.group.position.copy(start);
    chuteOpacity(chute, 0);
    scene.add(chute.group);
    flybys.push({ chute, t: 0, start, lean, phase: Math.random() * TAU });
  }

  function stepFlybys(dt) {
    sinceFlyby += dt;
    if (sinceFlyby >= FLYBY_EVERY) {
      sinceFlyby = 0;
      spawnFlyby();
    }
    for (const fly of [...flybys]) {
      fly.t += dt / FLYBY;
      const p = clamp01(fly.t);
      const { group, canopy } = fly.chute;
      group.position.set(
        fly.start.x - fly.lean * p * 1.6,
        fly.start.y - p * 5.2,
        fly.start.z,
      );
      group.rotation.z = Math.sin(elapsed * 1.6 + fly.phase) * 0.12;
      const b = Math.sin(elapsed * 3.1 + fly.phase) * 0.035;
      canopy.scale.set(1 + b, 1 - b, 1 + b);
      chuteOpacity(fly.chute, Math.min(1, p * 5, (1 - p) * 5));
      if (p >= 1) {
        disposeChute(fly.chute);
        flybys.splice(flybys.indexOf(fly), 1);
      }
    }
  }

  // --- Board events -------------------------------------------------------------------

  function dropCard() {
    const card = makeCard(0);
    card.drop = { t: 0, drift: (Math.random() - 0.5) * 2.4, phase: Math.random() * Math.PI * 2 };
    card.chute = makeChute();
    card.group.add(card.chute.group);
    const slot = slotOf(card);
    card.group.position.set(slot.x + card.drop.drift, DROP_HEIGHT, slot.z);
  }

  function advance(from) {
    const card = lanes[from].find((c) => !c.drop && !c.move);
    if (!card) return false;
    lanes[from].splice(lanes[from].indexOf(card), 1);
    card.column = from + 1;
    lanes[card.column].push(card);
    card.move = { from: card.group.position.clone(), t: 0 };
    paintCard(card);
    return true;
  }

  function trimDone() {
    const live = lanes[2].filter((c) => !c.sink);
    if (live.length <= MAX_IN_DONE) return;
    const oldest = live[0];
    oldest.sink = { t: 0 };
  }

  // Round robin, skipping whatever cannot happen right now.
  const ACTIONS = [
    () => lanes[0].length < 3 && (dropCard(), true),
    () => lanes[1].length > 0 && advance(1),
    () => lanes[1].length < 3 && advance(0),
  ];
  let nextAction = 0;
  function tick() {
    for (let n = 0; n < ACTIONS.length; n++) {
      const act = ACTIONS[(nextAction + n) % ACTIONS.length];
      if (act()) {
        nextAction = (nextAction + n + 1) % ACTIONS.length;
        break;
      }
    }
    trimDone();
  }

  // A board already in progress, so the first frame is a complete picture.
  for (const column of [0, 0, 1, 2, 2]) {
    const card = makeCard(column);
    card.group.position.copy(slotOf(card));
  }

  // --- Camera ------------------------------------------------------------------------

  let aspect = 1;
  let fitDistance = 10;
  const pointer = new THREE.Vector2();
  const pointerSmooth = new THREE.Vector2();

  // Three slow, out-of-step motions, so the shot never quite repeats: an
  // orbit around the board (about 24 degrees each way, every 26s), a push in
  // and out (19s), and a rise and fall (31s). The pointer leans on the orbit.
  const target = new THREE.Vector3(0, 0.1, 0.35);
  const shot = new THREE.Vector3();
  const opening = new THREE.Vector3();
  const TAU = Math.PI * 2;

  function placeCamera(time, introP) {
    const orbit = Math.sin((time * TAU) / 26) * 0.42 + pointerSmooth.x * 0.2;
    const radius = fitDistance * 0.8 * (1 - 0.1 * Math.sin((time * TAU) / 19));
    const height = 4.4 + Math.sin((time * TAU) / 31) * 0.8 + pointerSmooth.y * 0.6;
    shot.set(target.x + Math.sin(orbit) * radius, height, target.z + Math.cos(orbit) * radius);
    // The opening move: from low, close and off to the side, rising and
    // swinging round to the board.
    opening.set(target.x - 3.2, 1.6, target.z + fitDistance * 0.5);
    camera.position.lerpVectors(opening, shot, easeOutCubic(introP));
    camera.lookAt(target);
  }

  // --- The frame ----------------------------------------------------------------------

  const clock = new THREE.Clock(false);
  let elapsed = 0;
  let sinceTick = TICK * 0.7;
  let running = false;
  let raf = 0;

  function step(dt) {
    elapsed += dt;
    sinceTick += dt;
    if (sinceTick >= TICK) {
      sinceTick = 0;
      tick();
    }

    pointerSmooth.lerp(pointer, 1 - Math.exp(-dt * 3));
    const follow = 1 - Math.exp(-dt * 7);

    for (const card of [...cards]) {
      const slot = slotOf(card);
      const g = card.group;

      if (card.drop) {
        card.drop.t += dt / DROP;
        const p = clamp01(card.drop.t);
        const fall = 1 - easeOutCubic(p);
        const ph = card.drop.phase;
        g.position.set(slot.x + card.drop.drift * fall, DROP_HEIGHT * fall, slot.z);
        g.rotation.z = Math.sin(elapsed * 1.9 + ph) * 0.13 * fall;
        g.rotation.x = Math.sin(elapsed * 1.4 + ph) * 0.09 * fall;
        if (p >= 1) {
          card.drop = null;
          g.rotation.set(0, 0, 0);
          card.chute.liftT = 0;
          card.land = { t: 0 };
          spawnRing(slot);
        }
      } else if (card.move) {
        card.move.t += dt / MOVE;
        const p = clamp01(card.move.t);
        const e = easeInOutCubic(p);
        g.position.lerpVectors(card.move.from, slot, e);
        g.position.y = Math.sin(p * Math.PI) * 0.95;
        g.rotation.y = Math.sin(p * Math.PI) * 0.12;
        g.rotation.z = -Math.sin(p * Math.PI) * 0.06;
        if (p >= 1) {
          card.move = null;
          g.rotation.set(0, 0, 0);
        }
      } else if (card.sink) {
        card.sink.t += dt / SINK;
        const p = clamp01(card.sink.t);
        g.position.y = -0.5 * easeInQuad(p);
        setOpacity(card, 1 - p);
        if (p >= 1) {
          lanes[2].splice(lanes[2].indexOf(card), 1);
          removeCard(card);
          continue;
        }
      } else {
        // Settled: glide into its slot as the cards around it come and go.
        g.position.x += (slot.x - g.position.x) * follow;
        g.position.z += (slot.z - g.position.z) * follow;
        g.position.y += (0 - g.position.y) * follow;
      }

      if (card.land) {
        card.land.t += dt / LAND;
        const p = clamp01(card.land.t);
        const s = Math.sin(p * Math.PI) * (1 - 0.4 * p);
        squash(card, 1 - 0.45 * s, 1 + 0.05 * s);
        if (p >= 1) {
          card.land = null;
          squash(card, 1, 1);
        }
      }

      const chute = card.chute;
      if (chute && chute.liftT !== null) {
        // Landed: the canopy and its pear lift away and fade.
        chute.liftT += dt / LIFT_OFF;
        const p = clamp01(chute.liftT);
        chute.group.position.y = easeInQuad(p) * 3.4;
        chute.group.position.x = easeInQuad(p) * 1.2;
        chute.canopy.scale.set(1 + p * 0.15, 1 - p * 0.35, 1 + p * 0.15);
        chuteOpacity(chute, 1 - p);
        if (p >= 1) {
          disposeChute(chute);
          card.chute = null;
        }
      } else if (chute) {
        // Breathing in the wind on the way down.
        const b = Math.sin(elapsed * 3.1 + card.drop.phase) * 0.035;
        chute.canopy.scale.set(1 + b, 1 - b, 1 + b);
      }
    }

    for (const ring of [...rings]) {
      ring.t += dt / RING;
      const p = clamp01(ring.t);
      const grow = 0.55 + easeOutCubic(p) * 1.1;
      ring.mesh.scale.set(grow * 1.55, grow * 0.75, 1);
      ring.mesh.material.opacity = 0.45 * (1 - p);
      if (p >= 1) {
        ring.mesh.removeFromParent();
        ring.mesh.material.dispose();
        rings.splice(rings.indexOf(ring), 1);
      }
    }

    placeCamera(elapsed, clamp01(elapsed / INTRO));
    focusOn(dt);
    stepFlybys(dt);
  }

  // What the lens is on: the newest card still in the air, else a card
  // crossing between columns, else the middle of the board.
  const subject = new THREE.Vector3();
  let focusDistance = 11;
  function focusOn(dt) {
    const dropping = cards.filter((c) => c.drop).at(-1);
    const moving = cards.find((c) => c.move);
    if (dropping) dropping.group.getWorldPosition(subject);
    else if (moving) moving.group.getWorldPosition(subject);
    else subject.copy(target);
    const wanted = camera.position.distanceTo(subject);
    focusDistance += (wanted - focusDistance) * (1 - Math.exp(-dt * FOCUS_PULL));
  }

  function render() {
    if (dof) {
      bokeh.uniforms.focus.value = focusDistance;
      composer.render();
    } else {
      renderer.render(scene, camera);
    }
  }

  function loop() {
    raf = requestAnimationFrame(loop);
    // Capped, so a backgrounded tab returning does not fast-forward the board.
    step(Math.min(clock.getDelta(), 1 / 20) * TIME_SCALE);
    render();
  }

  // --- Paint ---------------------------------------------------------------------------

  function paintAll() {
    scene.background = colors.background;
    scene.fog.color.copy(colors.background);
    floorMat.opacity = colors.isLight ? 0.16 : 0.42;
    laneMat.color.copy(colors.surface);
    hemi.color.copy(colors.isLight ? new THREE.Color('#ffffff') : colors.ink);
    hemi.groundColor.copy(colors.background);
    hemi.intensity = colors.isLight ? 1.6 : 0.9;
    // Tinted, not saturated: enough cyan to edge the canopies.
    rim.color.copy(colors.primary).lerp(new THREE.Color('#ffffff'), 0.55);
    paintCanopy();
    drawHeaders();
    for (const card of cards) {
      paintCard(card);
      card.chute?.cords.material.color.copy(colors.ink);
    }
  }
  paintAll();

  // A still for reduced motion: the board, and one card on its way down.
  if (reducedMotion) {
    const card = makeCard(0);
    card.chute = makeChute();
    card.group.add(card.chute.group);
    const slot = slotOf(card);
    card.group.position.set(slot.x + 0.6, 3.1, slot.z);
    card.group.rotation.z = 0.06;
    elapsed = INTRO;
    placeCamera(INTRO, 1);
  }

  return {
    resize(width, height) {
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      composer.setSize(width, height);
      dof = width >= DOF_MIN_WIDTH;
      aspect = width / height;
      camera.aspect = aspect;
      camera.updateProjectionMatrix();
      // Far enough back that the board's width fits, however narrow the frame.
      const halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      fitDistance = Math.max(9.6, 6.4 / (halfH * aspect));
      // The fog keeps its distance from the camera, not the origin: on a
      // phone the camera sits far back and would otherwise see only fog.
      scene.fog.near = fitDistance + 3;
      scene.fog.far = fitDistance + 20;
      if (!running) {
        placeCamera(elapsed, reducedMotion ? 1 : clamp01(elapsed / INTRO));
        render();
      }
    },
    setPalette(p) {
      applyPalette(p);
      paintAll();
      if (!running) render();
    },
    setPointer(x, y) {
      pointer.set(x, y);
    },
    play() {
      if (running || reducedMotion) return;
      running = true;
      clock.start();
      loop();
    },
    pause() {
      running = false;
      cancelAnimationFrame(raf);
      clock.stop();
    },
    dispose() {
      this.pause();
      for (const card of [...cards]) {
        if (card.chute) disposeChute(card.chute);
        removeCard(card);
      }
      for (const header of headerMeshes) {
        header.material?.map?.dispose();
        header.material?.dispose();
      }
      for (const ring of rings) ring.mesh.material.dispose();
      for (const fly of flybys) disposeChute(fly.chute);
      for (const thing of owned) thing.dispose();
      bokeh.dispose();
      composer.dispose();
      renderer.dispose();
    },
  };
}
