"""Gera pathwaylog2foldchange3d.html — visão isométrica com barras 3D por idarea."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
PATHWAY_HTML = ROOT / "pathway.html"
CSV_PATH = ROOT / "silver_pathway_areasv1.csv"
OUTPUT = ROOT / "pathwaylog2foldchange3d.html"
PUBLIC_OUTPUT = REPO_ROOT / "public" / "index.html"
IMG_PATH = "map05171@2x_20260606_220006.png"
MAP_W_1X = 3538 / 2
MAP_H_1X = 5276 / 2


def load_area_data(csv_path: Path) -> dict[str, dict]:
    """Agrupa linhas do CSV por idarea (mesma lógica do overlay 2D)."""
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            buckets[row["idarea"]].append(row)

    result: dict[str, dict] = {}
    for area_id, rows in buckets.items():
        log2_values = [float(row["log2foldchange"]) for row in rows]
        symbols = [row["symbol"] for row in rows]
        pvalues = [float(row["pvalue"]) for row in rows]
        entries = [
            {
                "symbol": row["symbol"],
                "log2": float(row["log2foldchange"]),
                "pvalue": float(row["pvalue"]),
            }
            for row in rows
        ]
        result[area_id] = {
            "log2": sum(log2_values) / len(log2_values),
            "pvalue": min(pvalues),
            "symbols": symbols,
            "entries": entries,
        }
    return result


def parse_area_geometry(shape: str, coords: str) -> dict | None:
    parts = [float(v) for v in coords.split(",")]
    if shape == "circle" and len(parts) >= 3:
        cx, cy, r = parts[0], parts[1], parts[2]
        return {"cx": cx, "cy": cy, "w": r * 2, "h": r * 2, "shape": "circle"}
    if shape == "rect" and len(parts) >= 4:
        x1, y1, x2, y2 = parts[0], parts[1], parts[2], parts[3]
        return {
            "cx": (x1 + x2) / 2,
            "cy": (y1 + y2) / 2,
            "w": abs(x2 - x1),
            "h": abs(y2 - y1),
            "shape": "rect",
        }
    return None


def load_map_bounds(html_path: Path) -> tuple[float, float]:
    return MAP_W_1X, MAP_H_1X


def load_areas_from_html(
    html_path: Path, area_data: dict[str, dict]
) -> list[dict]:
    html = html_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'<area id="([^"]+)" shape="([^"]+)" data-coords="([^"]+)"'
    )
    areas: list[dict] = []

    for match in pattern.finditer(html):
        area_id, shape, coords = match.group(1), match.group(2), match.group(3)
        if area_id not in area_data:
            continue
        geom = parse_area_geometry(shape, coords)
        if not geom:
            continue
        data = area_data[area_id]
        log2 = data["log2"]
        areas.append(
            {
                "id": area_id,
                "symbols": data["symbols"],
                "entries": data["entries"],
                "log2": log2,
                "pvalue": data["pvalue"],
                "abs": abs(log2),
                "cx": geom["cx"],
                "cy": geom["cy"],
                "w": geom["w"],
                "h": geom["h"],
            }
        )

    return areas


def load_overlay_shapes(
    html_path: Path, area_data: dict[str, dict]
) -> list[dict]:
    html = html_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'<area id="([^"]+)" shape="([^"]+)" data-coords="([^"]+)"'
    )
    shapes: list[dict] = []

    for match in pattern.finditer(html):
        area_id, shape, coords = match.group(1), match.group(2), match.group(3)
        if area_id not in area_data:
            continue
        parts = [float(v) for v in coords.split(",")]
        if shape == "circle" and len(parts) < 3:
            continue
        if shape == "rect" and len(parts) < 4:
            continue
        data = area_data[area_id]
        shapes.append(
            {
                "id": area_id,
                "shape": shape,
                "coords": parts,
                "log2": data["log2"],
                "pvalue": data["pvalue"],
            }
        )

    return shapes


def render_html(
    areas: list[dict],
    overlay_shapes: list[dict],
    map_w: float,
    map_h: float,
) -> str:
    values = [a["log2"] for a in areas]
    log2_min = min(values)
    log2_max = max(values)
    abs_max = max(abs(log2_min), abs(log2_max))
    pvalues = [a["pvalue"] for a in areas]
    pvalue_min = min(pvalues)
    pvalue_max = max(pvalues)
    pvalue_min = min(pvalues)
    pvalue_max = max(pvalues)
    payload = json.dumps(areas, ensure_ascii=False)
    overlay_payload = json.dumps(overlay_shapes, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>map05171 — log2 fold change 3D isometric view</title>
<style>
* {{ box-sizing: border-box; }}
body {{
	margin: 0;
	font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
	background: #1a1f2e;
	color: #eee;
	overflow: hidden;
}}
#ui {{
	position: fixed;
	top: 0;
	left: 0;
	right: 0;
	z-index: 10;
	padding: 12px 16px 20px;
	background: linear-gradient(180deg, rgba(26,31,46,0.97) 85%, transparent);
	pointer-events: none;
}}
.filter-bar {{
	pointer-events: auto;
	margin-top: 12px;
	padding: 10px 12px;
	background: rgba(10, 12, 20, 0.72);
	border: 1px solid rgba(255,255,255,0.1);
	border-radius: 8px;
}}
.filter-bar label {{
	display: block;
	font-size: 12px;
	font-weight: 600;
	margin-bottom: 8px;
	color: #ccd;
}}
.filter-sliders {{
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 10px 16px;
}}
.filter-sliders .field {{
	display: flex;
	flex-direction: column;
	gap: 4px;
	font-size: 11px;
	color: #99a;
}}
.filter-sliders input[type="range"] {{
	width: 100%;
	accent-color: #6a9fd8;
}}
.filter-meta {{
	display: flex;
	align-items: center;
	gap: 12px;
	margin-top: 8px;
	font-size: 11px;
	color: #889;
	flex-wrap: wrap;
}}
.filter-meta button {{
	pointer-events: auto;
	padding: 4px 10px;
	font-size: 11px;
	border: 1px solid rgba(255,255,255,0.2);
	border-radius: 4px;
	background: rgba(255,255,255,0.06);
	color: #ccd;
	cursor: pointer;
}}
.filter-meta button:hover {{
	background: rgba(255,255,255,0.12);
}}
.project-about {{
	pointer-events: auto;
	max-width: 640px;
	background: rgba(15, 18, 28, 0.88);
	border: 1px solid rgba(255,255,255,0.12);
	border-radius: 8px;
	overflow: hidden;
}}
.project-about summary {{
	padding: 10px 12px;
	font-size: 12px;
	font-weight: 600;
	color: #ccd;
	cursor: pointer;
	list-style: none;
}}
.project-about summary::-webkit-details-marker {{
	display: none;
}}
.project-about summary::before {{
	content: '▸ ';
}}
.project-about[open] summary::before {{
	content: '▾ ';
}}
.about-body {{
	padding: 0 12px 12px;
	font-size: 12px;
	line-height: 1.55;
	color: #aab;
}}
.about-body p {{
	margin: 0 0 10px 0;
}}
.about-body ul {{
	margin: 6px 0 10px 0;
	padding-left: 18px;
}}
.about-body li {{
	margin-bottom: 3px;
}}
.about-body h1 {{
	margin: 0 0 6px 0;
	font-size: 18px;
	font-weight: 600;
	color: #eee;
}}
.about-body .intro {{
	margin: 0 0 12px 0;
	font-size: 13px;
	color: #aab;
}}
.about-body .legend {{
	margin-top: 4px;
}}
.export-bar {{
	pointer-events: auto;
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	margin-top: 8px;
	max-width: 640px;
}}
.export-bar button {{
	padding: 7px 12px;
	font-size: 11px;
	border: 1px solid rgba(255,255,255,0.22);
	border-radius: 6px;
	background: rgba(106, 159, 216, 0.18);
	color: #ddeeff;
	cursor: pointer;
}}
.export-bar button:hover {{
	background: rgba(106, 159, 216, 0.32);
}}
.legend {{
	display: flex;
	gap: 20px;
	flex-wrap: wrap;
	font-size: 12px;
}}
.legend-item {{
	display: flex;
	align-items: center;
	gap: 6px;
}}
.swatch {{
	width: 14px;
	height: 14px;
	border-radius: 2px;
	border: 1px solid rgba(255,255,255,0.3);
}}
.swatch.pos {{ background: #b2182b; }}
.swatch.neg {{ background: #2166ac; }}
#tooltip {{
	position: fixed;
	display: none;
	padding: 8px 10px;
	background: rgba(0,0,0,0.85);
	border: 1px solid #555;
	border-radius: 4px;
	font-size: 12px;
	pointer-events: none;
	z-index: 20;
	white-space: nowrap;
}}
#canvas-host {{
	width: 100vw;
	height: 100vh;
}}
#hint {{
	position: fixed;
	bottom: 12px;
	right: 16px;
	font-size: 11px;
	color: #889;
	z-index: 10;
}}
</style>
</head>
<body>
<div id="ui">
	<details class="project-about">
		<summary>About this project</summary>
		<div class="about-body">
			<h1>map05171 — 3D isometric log2 fold change bars</h1>
			<p class="intro">Bar height = |log2FC|. Red = up · Blue = down. Data: silver_pathway_areasv1.csv ({len(areas)} areas).</p>
			<p>
				This interactive visualization shows differential gene expression from the GEO dataset
				<strong>GSE251849</strong>, comparing <strong>healthy controls</strong> with individuals with
				<strong>long COVID</strong>. Pathway context is provided by the KEGG reference map
				<strong>map05171</strong> (Coronavirus disease).
			</p>
			<p>
				Developed for the course <strong>Science and Data Visualization in Healthcare</strong>
				(1s2026), taught by <strong>Prof. Dr. André Santanchè</strong> and
				<strong>Prof. Dr. Murilo Vieira Geraldo</strong>.
			</p>
			<p><strong>Team members:</strong></p>
			<ul>
				<li>Carlos Vinícius Araki Oliveira</li>
				<li>Carlos Eduardo Rosa Luengo</li>
				<li>Sabrina Tomaz Barbosa</li>
				<li>Luisa Freitas Colafati</li>
				<li>Maria Vitória Barbosa Valladares</li>
				<li>Muhammad Zuhair</li>
				<li>Mary Cristina Hernandez Xavier</li>
			</ul>
			<div class="legend">
				<div class="legend-item"><span class="swatch pos"></span> log2FC &gt; 0 (up to {log2_max:.2f})</div>
				<div class="legend-item"><span class="swatch neg"></span> log2FC &lt; 0 (down to {log2_min:.2f})</div>
			</div>
			<div class="filter-bar">
				<label for="pvalue-min">p-value filter (minimum p-value per area)</label>
				<div class="filter-sliders">
					<div class="field">
						<span>Minimum: <strong id="pvalue-min-label"></strong></span>
						<input type="range" id="pvalue-min" min="0" max="1000" value="0" step="1">
					</div>
					<div class="field">
						<span>Maximum: <strong id="pvalue-max-label"></strong></span>
						<input type="range" id="pvalue-max" min="0" max="1000" value="1000" step="1">
					</div>
				</div>
				<div class="filter-meta">
					<span id="pvalue-count"></span>
					<button type="button" id="pvalue-reset">Clear filter</button>
				</div>
			</div>
		</div>
	</details>
	<div class="export-bar">
		<button type="button" id="export-png">Export isometric view (PNG)</button>
		<button type="button" id="export-svg">Export flat pathway (SVG)</button>
	</div>
</div>
<div id="tooltip"></div>
<div id="hint">Drag to rotate · scroll to zoom</div>
<div id="canvas-host"></div>

<script type="importmap">
{{
  "imports": {{
    "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
  }}
}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

const AREAS = {payload};
const OVERLAY_SHAPES = {overlay_payload};
const MAP_W = {map_w};
const MAP_H = {map_h};
const ABS_MAX = {abs_max};
const LOG2_MIN = {log2_min};
const LOG2_MAX = {log2_max};
const PVALUE_DATA_MIN = {pvalue_min};
const PVALUE_DATA_MAX = {pvalue_max};
const PVALUE_PAD = 0.01e-5;
const PVALUE_FILTER_MIN = Math.max(0, PVALUE_DATA_MIN - PVALUE_PAD);
const PVALUE_FILTER_MAX = PVALUE_DATA_MAX + PVALUE_PAD;
const IMG = '{IMG_PATH}';

const PLANE_W = 40;
const PLANE_H = PLANE_W * (MAP_H / MAP_W);
const BAR_HEIGHT_SCALE = 6 / (ABS_MAX || 1);
const MIN_BAR = 0.08;

const host = document.getElementById('canvas-host');
const tooltip = document.getElementById('tooltip');

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a1f2e);
scene.fog = new THREE.Fog(0x1a1f2e, 80, 140);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 500);
const ISO_DIST = 55;
camera.position.set(ISO_DIST, ISO_DIST * 0.82, ISO_DIST);

const renderer = new THREE.WebGLRenderer({{ antialias: true, preserveDrawingBuffer: true }});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
host.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.target.set(0, 0, 0);
controls.minDistance = 20;
controls.maxDistance = 120;
controls.maxPolarAngle = Math.PI / 2.2;
controls.minPolarAngle = 0.35;
controls.update();

scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const sun = new THREE.DirectionalLight(0xffffff, 0.85);
sun.position.set(30, 50, 20);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
scene.add(sun);
const fill = new THREE.DirectionalLight(0xaaccff, 0.35);
fill.position.set(-20, 15, -25);
scene.add(fill);

const isoGroup = new THREE.Group();
isoGroup.rotation.x = -Math.PI / 2;
scene.add(isoGroup);

const barsGroup = new THREE.Group();
isoGroup.add(barsGroup);

const textureLoader = new THREE.TextureLoader();
textureLoader.load(IMG, function (texture) {{
	texture.colorSpace = THREE.SRGBColorSpace;
	texture.anisotropy = renderer.capabilities.getMaxAnisotropy();

	const planeGeo = new THREE.PlaneGeometry(PLANE_W, PLANE_H);
	const planeMat = new THREE.MeshStandardMaterial({{
		map: texture,
		roughness: 0.92,
		metalness: 0.02,
	}});
	const plane = new THREE.Mesh(planeGeo, planeMat);
	plane.receiveShadow = true;
	isoGroup.add(plane);

	const edgeGeo = new THREE.EdgesGeometry(planeGeo);
	const edge = new THREE.LineSegments(
		edgeGeo,
		new THREE.LineBasicMaterial({{ color: 0x334455, transparent: true, opacity: 0.5 }})
	);
	isoGroup.add(edge);

	buildBars();
	initPvalueFilter();
}});

initExportButtons();

const pvalueMinInput = document.getElementById('pvalue-min');
const pvalueMaxInput = document.getElementById('pvalue-max');
const pvalueMinLabel = document.getElementById('pvalue-min-label');
const pvalueMaxLabel = document.getElementById('pvalue-max-label');
const pvalueCount = document.getElementById('pvalue-count');
const pvalueReset = document.getElementById('pvalue-reset');
const PVALUE_SLIDER_STEPS = 1000;

function sliderToPvalue(step) {{
	const lo = Math.log10(PVALUE_FILTER_MIN || 1e-12);
	const hi = Math.log10(PVALUE_FILTER_MAX || 1);
	const t = step / PVALUE_SLIDER_STEPS;
	return Math.pow(10, lo + t * (hi - lo));
}}

function initPvalueFilter() {{
	pvalueMinInput.min = '0';
	pvalueMinInput.max = String(PVALUE_SLIDER_STEPS);
	pvalueMinInput.value = '0';
	pvalueMaxInput.min = '0';
	pvalueMaxInput.max = String(PVALUE_SLIDER_STEPS);
	pvalueMaxInput.value = String(PVALUE_SLIDER_STEPS);
	updatePvalueLabels();
	applyPvalueFilter();

	pvalueMinInput.addEventListener('input', function () {{
		if (Number(pvalueMinInput.value) > Number(pvalueMaxInput.value)) {{
			pvalueMinInput.value = pvalueMaxInput.value;
		}}
		updatePvalueLabels();
		applyPvalueFilter();
	}});
	pvalueMaxInput.addEventListener('input', function () {{
		if (Number(pvalueMaxInput.value) < Number(pvalueMinInput.value)) {{
			pvalueMaxInput.value = pvalueMinInput.value;
		}}
		updatePvalueLabels();
		applyPvalueFilter();
	}});
	pvalueReset.addEventListener('click', function () {{
		pvalueMinInput.value = '0';
		pvalueMaxInput.value = String(PVALUE_SLIDER_STEPS);
		updatePvalueLabels();
		applyPvalueFilter();
	}});
}}

function updatePvalueLabels() {{
	pvalueMinLabel.textContent = formatPvalue(sliderToPvalue(Number(pvalueMinInput.value)));
	pvalueMaxLabel.textContent = formatPvalue(sliderToPvalue(Number(pvalueMaxInput.value)));
}}

function applyPvalueFilter() {{
	const minP = sliderToPvalue(Number(pvalueMinInput.value));
	const maxP = sliderToPvalue(Number(pvalueMaxInput.value));
	let visible = 0;
	barMeshes.forEach(function (mesh) {{
		const p = mesh.userData.pvalue;
		const show = p >= minP && p <= maxP;
		mesh.visible = show;
		if (show) visible++;
	}});
	pvalueCount.textContent = visible + ' / ' + barMeshes.length + ' bars visible';
}}

function getActivePvalueRange() {{
	return {{
		min: sliderToPvalue(Number(pvalueMinInput.value)),
		max: sliderToPvalue(Number(pvalueMaxInput.value)),
	}};
}}

function downloadBlob(blob, fileName) {{
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = fileName;
	link.click();
	URL.revokeObjectURL(url);
}}

function colorForLog2Overlay(value) {{
	if (LOG2_MAX === LOG2_MIN) {{
		return 'rgba(200,200,200,0.62)';
	}}
	const t = (value - LOG2_MIN) / (LOG2_MAX - LOG2_MIN);
	const r = Math.round(33 + t * (178 - 33));
	const g = Math.round(102 + t * (24 - 102));
	const b = Math.round(172 + t * (43 - 172));
	return 'rgba(' + r + ',' + g + ',' + b + ',0.62)';
}}

function overlayShapeMarkup(shape) {{
	const color = colorForLog2Overlay(shape.log2);
	if (shape.shape === 'rect' && shape.coords.length >= 4) {{
		const x = Math.min(shape.coords[0], shape.coords[2]);
		const y = Math.min(shape.coords[1], shape.coords[3]);
		const w = Math.abs(shape.coords[2] - shape.coords[0]);
		const h = Math.abs(shape.coords[3] - shape.coords[1]);
		return (
			'<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h +
			'" fill="' + color + '" stroke="none" />'
		);
	}}
	if (shape.shape === 'circle' && shape.coords.length >= 3) {{
		return (
			'<circle cx="' + shape.coords[0] + '" cy="' + shape.coords[1] +
			'" r="' + shape.coords[2] + '" fill="' + color + '" stroke="none" />'
		);
	}}
	return '';
}}

function readImageAsDataUrl(url) {{
	return fetch(url)
		.then(function (response) {{ return response.blob(); }})
		.then(function (blob) {{
			return new Promise(function (resolve, reject) {{
				const reader = new FileReader();
				reader.onload = function () {{ resolve(reader.result); }};
				reader.onerror = reject;
				reader.readAsDataURL(blob);
			}});
		}});
}}

function exportIsometricPng() {{
	renderer.render(scene, camera);
	downloadBlob(
		dataUrlToBlob(renderer.domElement.toDataURL('image/png')),
		'map05171-isometric-log2fc.png'
	);
}}

function dataUrlToBlob(dataUrl) {{
	const parts = dataUrl.split(',');
	const mime = parts[0].match(/:(.*?);/)[1];
	const binary = atob(parts[1]);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) {{
		bytes[i] = binary.charCodeAt(i);
	}}
	return new Blob([bytes], {{ type: mime }});
}}

async function exportPathwaySvg() {{
	const range = getActivePvalueRange();
	const imageDataUrl = await readImageAsDataUrl(IMG);
	const overlayParts = OVERLAY_SHAPES
		.filter(function (shape) {{
			return shape.pvalue >= range.min && shape.pvalue <= range.max;
		}})
		.map(overlayShapeMarkup)
		.filter(Boolean);

	const svg =
		'<?xml version="1.0" encoding="UTF-8"?>' +
		'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ' +
		'width="' + MAP_W + '" height="' + MAP_H + '" viewBox="0 0 ' + MAP_W + ' ' + MAP_H + '">' +
		'<image href="' + imageDataUrl + '" x="0" y="0" width="' + MAP_W + '" height="' + MAP_H + '" />' +
		overlayParts.join('') +
		'</svg>';

	downloadBlob(
		new Blob([svg], {{ type: 'image/svg+xml;charset=utf-8' }}),
		'map05171-log2fc-pathway.svg'
	);
}}

function initExportButtons() {{
	document.getElementById('export-png').addEventListener('click', exportIsometricPng);
	document.getElementById('export-svg').addEventListener('click', function () {{
		exportPathwaySvg().catch(function (err) {{
			console.error(err);
			alert('Could not export SVG. Please try again.');
		}});
	}});
}}

function mapX(cx) {{
	return (cx / MAP_W - 0.5) * PLANE_W;
}}
function mapY(cy) {{
	return (0.5 - cy / MAP_H) * PLANE_H;
}}

function formatPvalue(value) {{
	if (value < 0.001) return value.toExponential(2);
	return value.toFixed(4);
}}

function formatTooltip(area) {{
	if (area.entries.length === 1) {{
		var e = area.entries[0];
		return (
			'<strong>' + e.symbol + '</strong><br>' +
			'log2FC: ' + e.log2.toFixed(3) + '<br>' +
			'|log2FC|: ' + Math.abs(e.log2).toFixed(3) + '<br>' +
			'p-value: ' + formatPvalue(e.pvalue)
		);
	}}
	return area.entries.map(function (e) {{
		return '<strong>' + e.symbol + '</strong>: log2 ' + e.log2.toFixed(3) + ', p ' + formatPvalue(e.pvalue);
	}}).join('<br>');
}}

function colorForLog2(value) {{
	return value >= 0 ? 0xb2182b : 0x2166ac;
}}

const barMeshes = [];

function buildBars() {{
	const sorted = AREAS.slice().sort(function (a, b) {{ return a.abs - b.abs; }});

	sorted.forEach(function (area) {{
		const barW = Math.max(0.15, Math.min(0.55, (area.w / MAP_W) * PLANE_W * 0.85));
		const barD = Math.max(0.15, Math.min(0.55, (area.h / MAP_H) * PLANE_H * 0.85));
		const height = Math.max(MIN_BAR, area.abs * BAR_HEIGHT_SCALE);

		const geo = new THREE.BoxGeometry(barW, barD, height);
		geo.translate(0, 0, height / 2);

		const mat = new THREE.MeshStandardMaterial({{
			color: colorForLog2(area.log2),
			roughness: 0.45,
			metalness: 0.08,
		}});
		const mesh = new THREE.Mesh(geo, mat);
		mesh.position.set(mapX(area.cx), mapY(area.cy), 0.01);
		mesh.castShadow = true;
		mesh.receiveShadow = true;
		mesh.userData = area;
		barsGroup.add(mesh);
		barMeshes.push(mesh);
	}});
}}

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function onPointerMove(event) {{
	pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
	pointer.y = -(event.clientY / window.innerHeight) * 2 + 1;
	raycaster.setFromCamera(pointer, camera);
	const hits = raycaster.intersectObjects(barMeshes, true).filter(function (h) {{
		return h.object.visible;
	}});
	if (hits.length) {{
		const a = hits[0].object.userData;
		tooltip.style.display = 'block';
		tooltip.style.left = (event.clientX + 12) + 'px';
		tooltip.style.top = (event.clientY + 12) + 'px';
		tooltip.innerHTML = formatTooltip(a);
		renderer.domElement.style.cursor = 'pointer';
	}} else {{
		tooltip.style.display = 'none';
		renderer.domElement.style.cursor = 'grab';
	}}
}}

renderer.domElement.addEventListener('pointermove', onPointerMove);

function onResize() {{
	camera.aspect = window.innerWidth / window.innerHeight;
	camera.updateProjectionMatrix();
	renderer.setSize(window.innerWidth, window.innerHeight);
}}
window.addEventListener('resize', onResize);

function animate() {{
	requestAnimationFrame(animate);
	controls.update();
	renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>
"""


def main() -> None:
    area_data = load_area_data(CSV_PATH)
    map_w, map_h = load_map_bounds(PATHWAY_HTML)
    areas = load_areas_from_html(PATHWAY_HTML, area_data)
    overlay_shapes = load_overlay_shapes(PATHWAY_HTML, area_data)
    html = render_html(areas, overlay_shapes, map_w, map_h)
    OUTPUT.write_text(html, encoding="utf-8")
    PUBLIC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_OUTPUT.write_text(html, encoding="utf-8")
    print(
        f"Gerado {OUTPUT} e {PUBLIC_OUTPUT} "
        f"({len(areas)} barras 3D, mapa {map_w:.0f}×{map_h:.0f})"
    )


if __name__ == "__main__":
    main()
