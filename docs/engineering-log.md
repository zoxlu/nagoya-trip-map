# Engineering Log — Nagoya Trip Map

Twenty-seven things that went wrong while building the [Nagoya trip map](../README.md), what caused each one, and the general rule I took away.

They are grouped by **root cause**, not by date. Read in date order, a log like this says "many things broke". Grouped, it says which *kinds* of things break — and that is what carries over to the next project.

| Family | Entries | What they have in common |
|---|---|---|
| [Silent failures](#1-silent-failures) | 1–5, 26 | No error. The screen looks normal. The result is wrong. |
| [Coordinates and space](#2-coordinates-and-space) | 6–8 | The same location means different things at different stages. |
| [Curves and geometry](#3-curves-and-geometry) | 9–10 | The mathematical definition decides the outcome, not the parameters. |
| [Visual judgement](#4-visual-judgement) | 11–13, 27 | A difference that exists in the data but not to the eye. |
| [Library behaviour](#5-library-behaviour) | 14–16 | Defaults and types that differ from intuition. |
| [Environment and deployment](#6-environment-and-deployment) | 17–22 | Works locally ≠ works deployed. |
| [Changes that miss a spot](#7-changes-that-miss-a-spot) | 23–25 | Editing line by line, one line gets left behind. |

Silent failures are the largest family and the most dangerous, because nothing forces you to deal with them. The habit that answers them runs through the whole log: **every transform and every filter prints numbers, so the data can speak for itself.**

Each entry follows the same shape: **Symptom → Cause → Fix → Rule.**

---

## 1. Silent failures

### 1 · A duplicated property broke the whole block

**Symptom.** After replacing a `getFillColor` accessor, the layer stopped working.

**Cause.** The old line was never deleted, so the object had two `getFillColor` properties — and the new one was missing its trailing comma. Duplicate keys are legal in a JavaScript object literal (the later one silently wins), which is why the duplication itself raised no warning.

**Fix.** Delete the old line; add the comma.

**Rule.** When handing over or applying a replacement snippet, say explicitly which lines it replaces. And an error's line number marks where parsing *stopped* making sense — the real problem is often a line or two above.

### 2 · ⭐ Assuming the shape of the data dropped half of it

**Symptom.** The map rendered normally.

**Cause.** The first version of the conversion script accepted only `type: place`, because that was the type of the one note I had looked at. It silently skipped 82 notes of `type: food` and later 15 of `type: supermarket` — and restaurants stored their category in `food_category`, not `place_category`.

**Fix.** The script now reports the distribution of types, categories and days on every run, plus what it skipped and why.

**Rule.** Explore the data statistically *before* writing the transform. This is the most dangerous kind of error: the map still displays, just with half the data missing, and nothing ever complains.

### 3 · ⭐ Filters did nothing: `updateTriggers`

**Symptom.** Clicking a filter button changed nothing — no colour change, no size change, no error.

**Cause.** For performance, deck.gl caches the results of `getXxx` accessors and recomputes them only when `data` changes. Here the data had not changed; an external state variable (`filter`) had.

**Fix.**

```js
updateTriggers: {
  getRadius: filter,
  getFillColor: filter
}
```

**Rule.** If an accessor reads anything other than `data`, that variable must be listed in `updateTriggers`. Several variables go in an array.

**The same bug, later, in my own code.** Label de-confliction needs to rerun on every camera move, but the route geometry — seven days of spline evaluation — does not. I memoised the routes behind an explicit key:

```js
function getRoutes() {
  const key = `${filter}|${showArcs}`;
  if (routeCacheKey === key) return routeCache;
  // ...recompute...
}
```

That key is a declaration of *what the result depends on*. Add a new input that affects routes — say, a slider for the curve's bow — and forget to add it to the key, and the slider will do nothing, silently. `updateTriggers` and a memoisation key are the same idea: **hand-declared dependencies**. Houdini maintains a dependency graph for you; here it is your job.

### 4 · ⭐ A derived number hid upstream damage

**Symptom.** None. The script produced 141 places, exactly as before.

**Cause.** One note's entire frontmatter had been accidentally deleted in the working tree (not yet committed). With no `location` or `type`, the script skipped it — and skipping is its normal behaviour. I found it only by checking every change in `git status` that I had not made myself, before committing. Restored: 141 → 142.

**Fix.** Restore the file — after first backing up the damaged version and confirming with `git diff --numstat` that restoring would lose no added lines.

**Rule.** A variant of entry 2: the same number means different things at different times. 141 had been correct once, which is exactly what made it believable. Before committing, understand every change in `git status` that you did not cause; never just `git add .`.

### 5 · ⭐ A library feature removed every label

**Symptom.** Enabling deck.gl's `CollisionFilterExtension` to stop labels overlapping made **all** labels disappear — even on a day with two places and plenty of space. Not over-filtering; the whole layer was gone.

**Cause.** Unknown. The development environment gave me no way to inspect the extension's internal behaviour, so further guessing at configuration was a dead end.

**Fix.** A self-written screen-space greedy algorithm (project candidates to screen, keep the highest-priority label in each area). Crucially, it was written as a standalone function that could be extracted from the HTML and run in Node against the real data:

```
zoom 10:  overview  5/30 | Day1 1/2 | Day3 1/8 | Day5 2/9
zoom 12:  overview 10/30 | Day1 2/2 | Day3 2/8 | Day5 3/9
zoom 14:  overview 21/30 | Day1 2/2 | Day3 5/8 | Day5 6/9
zoom 16:  overview 28/30 | Day1 2/2 | Day3 8/8 | Day5 9/9
```

**Rule.** When you cannot observe a system directly, prefer an algorithm you can verify with numbers over a black box that is convenient until it isn't. Its collision shape was refined twice afterwards — see entries 12 and 13.

### 26 · ⭐ The statistics only counted what got in

*Found later; filed with its family.*

**Symptom.** None, again.

**Cause.** The conversion script reports the distribution of everything it collected — the fix from entry 2. But two paths still left no trace: a note with no readable frontmatter, and a note whose `type` was outside the three the script accepts. Both were a bare `continue`. So if a new type is ever added to the notes (a hotel, a shop), every note of that type disappears from the output and from the statistics at the same time. Entry 2 fixed the symptom I had hit; it did not fix the *shape* of the gap.

**Fix.** Count every file scanned, tally every `type` seen including the rejected ones, keep the filenames for each exclusion reason, and reconcile:

```
掃到 .md    : 172 個檔案
寫入        : 142 筆
未收        : 30 筆
  - no-frontmatter     :  1 筆 · 天守閣.md
  - type-not-collected : 25 筆 · Home.md, By-District.md, ...
  - no-valid-location  :  4 筆 · 黑豚木曾路.md, ...
掃到的 type(含未收): {'(no type)': 16, 'place': 45, 'supermarket': 15,
                      'food': 86, 'accommodation': 6, 'transport': 3}
⚠️  有 25 筆的 type 不在收取清單內
```

If collected + excluded ≠ scanned, the script says so — that means a code path exists which nobody is counting.

The first run found two things the old script had been hiding: a note whose frontmatter was missing, and a restaurant with no usable coordinates that should have been on the map. It also surfaced two types nobody had thought about — the accommodation notes (the map still hard-codes its start point) and transport notes. None of these had ever produced an error.

**Rule.** Statistics that only summarise the accepted rows cannot show you what never arrived. A pipeline should be able to account for every input it saw, and every rejection needs a reason and a name attached. This is entry 2's blind spot, one stage upstream: I had fixed the instance, not the class.


---

## 2. Coordinates and space

### 6 · `[lng, lat]` is the reverse of what people write

**Symptom.** A classic: points land on the other side of the planet.

**Cause.** The notes store locations as `"lat,lng"` (e.g. `35.05056,136.84333`), the way map apps display them. GeoJSON and deck.gl require **longitude first**.

**Fix.** The conversion script splits and swaps the pair, and range-checks every coordinate (−90 ≤ lat ≤ 90, −180 ≤ lng ≤ 180) to catch reversed entries.

**Rule.** Coordinate order is the most common beginner error in geospatial work. Convert once, at the boundary, and validate there.

### 7 · Raised geometry hides ground-level layers

**Symptom.** After tilting the camera and extruding columns, some labels and markers were hidden behind the columns.

**Cause.** In a tilted view, 3D geometry occludes 2D elements drawn at ground level.

**Fix.** Elements that belong to an object — its label, its marker — are raised to the same height as the object.

**Rule.** Once a dataset gains a third dimension, every element attached to it has to move into that dimension too.

### 8 · Screen-space algorithms must project where things are *drawn*

**Symptom.** After the columns went up, label de-confliction started making odd choices. No errors — it just looked slightly wrong.

**Cause.** `map.project()` given a 2D coordinate returns the ground point. Once labels sat on top of columns, the ground point and the displayed position were no longer the same, so every overlap test was computed against positions that were not on screen.

**Fix.** Project the 3D top position. And because the column height, the label position and the de-confliction must all agree on where "the top" is, all three call one function:

```js
const COLUMN_SCALE = 180;

function topPosition(d) {
  return [d.position[0], d.position[1], (d.interest ?? 1) * COLUMN_SCALE + 120];
}
```

**Rule.** The 3D version of single source of truth (entry 24). In 2D, a duplicated fact was one colour written twice — easy to spot. In 3D it becomes one position computed three times, and inconsistency shows up as a small geometric offset: never wildly wrong, which is exactly why it is hard to notice.

---

## 3. Curves and geometry

### 9 · ⭐ Approximating curves do not pass through their control points

**Symptom.** Daily routes, smoothed with Chaikin subdivision, looked good but ran *beside* the places they connected instead of through them.

**Cause.** Chaikin is corner-cutting: each iteration replaces a vertex with two points near it, so the curve converges towards the control polygon without ever touching its vertices. It is an **approximating** curve, like B-splines and the interior control points of a Bézier curve.

**Fix.** Catmull-Rom, an **interpolating** spline that passes through every control point by definition. Measured deviation at every stop: **0.00 m**.

**Rule.** Splines divide into two families — interpolating (Catmull-Rom, natural cubic) and approximating (B-spline, Chaikin, Bézier's interior points). If the curve must reach real locations, it must be interpolating. No parameter fixes this; it is the definition of the curve.

### 10 · The parameterisation decides whether the curve knots itself

**Symptom.** With uniform Catmull-Rom, some routes overshot or looped on themselves.

**Cause.** Uniform parameterisation behaves badly when segment lengths differ greatly — and here they range from about 300 m inside the city to 25 km out to Inuyama, nearly a factor of a hundred.

**Fix.** **Centripetal** parameterisation (α = 0.5), which exists precisely to prevent cusps and self-intersection. The knot spacing grows with the square root of the distance between points:

```js
const knot = (ti, a, b) => ti + Math.sqrt(Math.hypot(b[0] - a[0], b[1] - a[1]));
```

Measured: curves are 4–8% longer than the straight polyline — rounded, without overshoot.

**Rule.** Catmull-Rom has three standard parameterisations: uniform (α = 0), centripetal (α = 0.5), chordal (α = 1). With unevenly spaced points, use centripetal.

**Related technique.** Out-and-back legs along the same road would collapse into one line. Each segment's midpoint is pushed to the *left of the direction of travel* by a fraction of the segment's length. Outbound and return legs travel in opposite directions, so they bow apart into a lens automatically — the geometry handles the special case with no special-case code. Because the bow is relative, a 300 m segment bows by 45 m and a 25 km segment by 3.7 km, and both look equally curved.

---

## 4. Visual judgement

### 11 · A numeric difference is not a visible difference

**Symptom.** Interest levels were encoded as colour, and every point looked the same.

**Cause.** `[255, 140 - interest * 25, 0]` — across the three interest levels the green channel changes by only 50. Real in the data, invisible to the eye.

**Fix.** Normalise the data to 0–1 first, then map that range onto the full perceptible span of the colour scale.

**Rule.** A colour mapping must stretch the data across the perceptible colour space, or the encoding does not exist. Normalise-then-map is the universal skeleton for every visual channel — size, colour, height, opacity — and it is Houdini's `fit()`. Size differences are also easier to perceive than colour differences.

### 12 · A circular collision test over-penalises flat labels

*Superseded by entry 13; kept because the progression is the point.*

**Symptom.** The first de-confliction (entry 5) used a circular test with a 46 px radius and removed labels that were clearly readable — ones offset vertically from each other.

**Cause.** Labels are much wider than tall. A circle wastes most of the available space in the short direction.

**Fix.** An elliptical test (72 × 24 px): `Math.hypot(dx / gapX, dy / gapY) >= 1`. On Day 1 at zoom 12, visible labels went from one to two.

**Rule.** The collision shape should match the shape of the thing being tested.

### 13 · ⭐ Shape, size, and change with zoom — all three have to fit

**Symptom.** The ellipse was still one size for every label, fixed in pixels. Labels whose widths differed by a factor of three shared one box — too cautious for short labels, useless for long ones. And because label size is set in metres, font size changes with zoom, so any fixed pixel box goes wrong at some zoom level.

**Fix.** Compute each label's actual rectangle and use an axis-aligned overlap test:

```js
// Rendered font size: sizeUnits is 'meters', so pixel size changes with zoom
function labelFontPx() {
  const lat = map.getCenter().lat;
  const mpp = 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, map.getZoom());
  return Math.min(17, Math.max(10, 120 / mpp));   // must match getSize: 120 and min/max
}

// Full-width CJK characters ≈ 1 em, half-width ≈ 0.55 em
const cjk = (d.name.match(/[\u3000-\u9fff\uff00-\uffef]/g) || []).length;
const w = cjk * fontPx + (d.name.length - cjk) * fontPx * 0.55 + 12;
const h = fontPx + 8;

const clear = boxes.every(b =>
  Math.abs(p.x - b.x) > (w + b.w) / 2 ||
  Math.abs(p.y - b.y) > (h + b.h) / 2
);
```

- **Font size** is derived from metres-per-pixel at the current zoom, clamped exactly as the layer clamps it. The numbers must match the layer's `getSize`, or the boxes describe labels that do not exist on screen (entry 24's family).
- **Width and height** are estimated per label from its characters; `+12` and `+8` cover the background padding (`[5, 2, 5, 2]`) plus a little breathing room.
- **The test** is the 2D case of the separating axis theorem: two rectangles do not overlap if they are separated on either axis. `every` + `||` says exactly that.

**Rule.** A collision test must be at least as fine-grained as the variation in the objects it tests: if shapes differ, match the shape; if sizes differ, compute per object; if size changes with the view, recompute per view. Circle → ellipse → rectangle was the same rule applied three times, each time a little closer. The best-fitting shape is usually the one actually drawn: these labels render with a padded rectangular background, so the rectangle is not an approximation.

### 27 · The box was the right shape and size, in the wrong place

*Found later; filed with its family.*

**Symptom.** Screenshots of the overview still showed labels overlapping — always one above another, never side by side.

**Cause.** The de-confliction centres each box on the projected anchor point. But the layer draws the label *above* that point: `getPixelOffset: [0, -16]` shifts it up, and `getAlignmentBaseline: 'bottom'` puts the text's bottom edge at the anchor. So the rectangle that is actually painted sits roughly `16 + h/2` pixels above the rectangle being tested. Horizontally the two agree — the anchor is `middle` — which is exactly why every collision that slipped through was vertical.

**Fix.** Test the box where it is drawn:

```js
const cy = p.y - 16 - h / 2;   // pixelOffset + bottom baseline
```

and compare on `cy` instead of `p.y`.

**Rule.** Three things have to match between a collision test and the object it guards: shape (entry 12), size (entry 13), and **position**. Render-time offsets — pixel offsets, anchors, baselines — move the drawn object without moving the data point it came from. Same family as entry 8, one stage later: entry 8 was about projecting the right position in 3D, this one is about the 2D offsets applied after projection.


---

## 5. Library behaviour

### 14 · Layer-level opacity interfered with per-point alpha

**Symptom.** Unplanned places were meant to be faded, via a fourth (alpha) value in `getFillColor`. The fade did not show as intended.

**Cause.** A layer-level `opacity: 0.85` was interfering with the per-point alpha.

**Fix.** Remove the layer's `opacity` and let each point's own alpha carry all transparency.

**Rule.** When the same property can be set at two levels, decide which level owns it and set it only there.

### 15 · Chinese and Japanese labels rendered as blanks

**Symptom.** TextLayer showed empty space or boxes for every CJK label.

**Cause.** By default TextLayer builds its font atlas from ASCII only.

**Fix.** `characterSet: 'auto'`, which scans the data for the characters actually used.

**Rule.** Easy to miss in the documentation, but required for any CJK data.

### 16 · ⭐ PathLayer lies flat — and has no `getHeight`

**Symptom.** After tilting the camera, labels and markers looked three-dimensional; the routes stayed flat on the ground. Adjusting `getHeight` did nothing.

**Cause.** When the routes moved from `ArcLayer` to `PathLayer` (for the smooth loops in entries 9–10), `getHeight` stopped existing. ArcLayer's arc is built-in geometry; PathLayer just joins the points it is given, on the ground plane by default.

**Fix.** PathLayer accepts `[lng, lat, z]` points. Add a z value when generating each segment; the spline code is untouched:

```js
const ARC_LIFT = 900;   // metres at the top of each arc

const path = flat.map((p, i) => {
  const t = i / (flat.length - 1);
  return [p[0], p[1], Math.sin(Math.PI * t) * ARC_LIFT];
});
```

`sin(πt)` is 0 at both ends and 1 in the middle, so every segment lands exactly on its stops and arches between them — entry 9's "passes through every stop" still holds. `billboard: true` keeps the line facing the camera so it does not thin out in the tilted view.

**Rule.** Changing layer type is not a rename; the set of geometric properties it supports changes too. The symptom is a parameter that does nothing, not an error.

---

## 6. Environment and deployment

### 17 · `fetch()` fails when the page is opened from disk

**Cause.** Browsers do not let a `file://` page read other local files (CORS).

**Fix.** Serve it: `python3 -m http.server 8000`, then open `localhost:8000`.

### 18 · Chinese text became mojibake

**Symptom.** `é¡žåˆ¥` where the category name should be.

**Cause.** The HTML declared no encoding, so the browser decoded UTF-8 bytes with its default.

**Fix.** `<meta charset="UTF-8">` at the top of the page.

**Rule.** Encoding bugs look like "the logic is perfect but the text is garbage", and they never raise an error — decoding bytes with the wrong encoding is a perfectly legal operation. Same family as a Unicode normalisation bug I hit in an earlier project.

### 19 · ⭐ Absolute paths break under a sub-path site

**Cause.** The site's base URL is `zoxlu.github.io/Notes-for-trips`, so its root is `/Notes-for-trips/`. A link to `/static/trip-map/` would point at `zoxlu.github.io/static/...` and fail. It worked only because the site framework's link transformer rewrote it to a relative path.

**Rule.** GitHub Pages project sites live under `/<repo>/`. Local testing at the server root will never reveal this. Any absolute path deserves a second thought.

### 20 · ⭐ Escaping the single-page-app router: read the source

**Symptom.** Links to the map were intercepted by the site's client-side router. An attribute that was supposed to opt out (`data-router-ignore`) had no effect.

**Fix.** Instead of guessing further, I read the router's click handler. One line decides it:

```js
if (target.attributes.getNamedItem("target")?.value === "_blank") return
```

Links with `target="_blank"` are not intercepted. Note that it checks the **event target** — the exact element clicked — not `closest("a")`. So the link must not wrap child elements like a `<span>`, or clicks on the child slip past the check.

**Rule.** Rather than guessing whether an attribute works, read the interception logic. A framework's escape hatch is usually in those five lines.

### 21 · A fake 404 from the test server

**Symptom.** Links on the site returned 404 when tested locally.

**Cause.** The framework writes internal links without extensions (`.../By-District` for `By-District.html`). GitHub Pages and the framework's own dev server add `.html`; `python -m http.server` does not. The files were fine.

**Diagnosis.** Test an existing link I had never touched, the same way. It failed too — so the problem was the tool, not my change.

**Rule.** When something new breaks, test something known to work with the same method. If both break, suspect the environment.

### 22 · On mobile, `viewport` is the master switch

**Symptom.** On a phone, the map was a small rectangle in the middle of the screen.

**Cause.** No `<meta name="viewport">`. Without it, phones render the page at a virtual 980 px width and scale it down.

**Fix.** Add the tag, and then the rest of the mobile work:

| Problem | Fix |
|---|---|
| `100vh` pushed below the address bar | `100dvh` |
| Buttons too small to tap | `min-height: 36px` |
| Legend covering the map | Moved to bottom-left and shrunk on narrow screens |
| Keyboard hints meaningless on touch | Hidden on small screens |
| `fitBounds` reserving 240 px for a legend that isn't there | Padding computed from screen width |

**Rule.** `viewport` is not an optimisation; it is the switch. Without it, all other responsive work is wasted.

---

## 7. Changes that miss a spot

### 23 · An elided snippet deleted a layer

**Symptom.** Routes appeared, but every point marker vanished.

**Cause.** A code snippet (AI-generated) replaced an unchanged section with `// ...rest unchanged...`. When I merged it, that section did not survive.

**Rule.** When a snippet elides content, confirm afterwards that the elided part is really still there. Better: ask for complete functions, not fragments.

### 24 · The same magic number in two places

**Symptom.** Caught before it caused a bug: the restroom colour `rgb(150, 100, 190)` was hard-coded in both the layer and the legend. Changing it would have meant changing it twice.

**Fix.** `const RESTROOM_COLOR = [150, 100, 190]`, referenced by both. More generally, colours are defined once in a named table and the legend is generated from that same table.

**Rule.** Single source of truth: one fact lives in one place. It is also why `spots.json` is never edited by hand — the notes are the source; the JSON is derived.

### 25 · A partial rename and the temporal dead zone

**Symptom.** `ReferenceError: Cannot access 'path' before initialization`.

**Cause.** Renaming a variable from `path` to `flat` (so `path` could hold the version with heights), one reference was missed:

```js
if (nextStart) path.push(nextStart);   // ← path not declared yet

const path = flat.map(...);            // ← declared here
```

`const` and `let` are in a *temporal dead zone* until their declaration — unlike `var`, touching them early is an error, not `undefined`. The logic was also wrong: `nextStart` belongs on `flat`, before heights are added.

**Rule.** Rename with the editor's replace-all, not by hand. When only some occurrences should change, copy the whole block out, edit it, and paste it back. Like entry 23: editing line by line is where lines get left behind.

---

## Design decisions

Not failures, but judgements that shaped the map.

- **Ask what a view is for before choosing what to encode.** The seven-day overview uses a single muted colour for all routes. Seven colours would exceed comfortable discrimination, and the categories already use three hues. The overview answers "what shape is the whole trip?"; "which day is this?" is what single-day mode is for.
- **Encoding should be honest to reality.** An early version drew arcs radiating from the hotel to every stop. That shows distance, not a day. A real day is a loop — hotel → A → B → C → hotel — so the routes became loops.
- **Confirmed information is shown; uncertain information is revealed on interaction.** Planned places are labelled directly; candidates show details on interaction. Hover does not exist on a phone, and phones are where the map is used.
- **Orthogonal visual channels.** Hue = category; size, lightness and outline = planned or not; height = interest. One channel per dimension, so two dimensions can be read at once.
- **Perceptually distinct, not just different.** Restrooms were blue — too close to the blue used for sights — so they became purple, which sits far from every other hue in use and is safer for red–green colour blindness.
- **Density is a design choice.** 142 places × several nearby restrooms would be 500+ markers. Restrooms appear only around the currently highlighted places, de-duplicated by coordinate.
- **Separate what depends on the camera from what doesn't.** Labels must be recomputed on every move; routes need not be (entry 3).
- **Isolation can be cheap.** The map lives in a static folder the site framework copies verbatim — no framework build, styling or routing touches it. Isolation was verified by byte-level `diff` of source against build output, not by eye: a page that looks right may only be lucky.
- **"Works" and "verified" are different claims.** Where something could be checked — HTTP status, valid JSON, syntax, byte equality, numeric output of the geometry — it was. Where it couldn't in this environment, that was stated rather than folded into "done".
