import fs from "fs";
import { feature, mesh } from "/tmp/claude-0/work/npm/node_modules/topojson-client/src/index.js";
import { geoPath } from "/tmp/claude-0/work/npm/node_modules/d3-geo/src/index.js";
const topo = JSON.parse(fs.readFileSync("/tmp/claude-0/work/npm/node_modules/us-atlas/counties-albers-10m.json"));
const csv = fs.readFileSync("/home/claude/votecalculator/voter_turnout_data.csv", "utf8").trim().split("\n");
const head = csv[0].split(",");
const iF = head.indexOf("FIPS"), iV = head.indexOf("Vote Power 2022");
const vp = {};
for (const line of csv.slice(1)) { const c = line.split(","); vp[c[iF]] = parseFloat(c[iV]); }
const RAMP = ["#B7A9EE", "#937FE0", "#6E54C9", "#4B30A3", "#24135F"];
const BREAKS = [1.75, 2.0, 2.5, 3.0];
const color = v => v == null || isNaN(v) ? "#D9D6E0" : RAMP[BREAKS.filter(b => v >= b).length];
const path = geoPath();
const counties = feature(topo, topo.objects.counties).features;
let missing = [], paths = "";
for (const f of counties) {
  let id = f.id;
  let v = vp[id];
  if (id.startsWith("02")) v = vp["02000"];
  if (id === "15005") v = vp["15009"];
  if (v === undefined) missing.push(id);
  paths += `<path d="${path(f)}" fill="${color(v)}"/>`;
}
const states = path(mesh(topo, topo.objects.states, (a, b) => a !== b));
const nation = path(mesh(topo, topo.objects.nation));
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 975 610"><g stroke="#FFFFFF" stroke-width="0.25" stroke-linejoin="round">${paths}</g><path d="${states}" fill="none" stroke="#FFFFFF" stroke-width="1.1" stroke-linejoin="round"/><path d="${nation}" fill="none" stroke="#17112E" stroke-width="0.6"/></svg>`;
fs.writeFileSync("/tmp/claude-0/work/map.svg", svg);
console.log("counties drawn", counties.length, "missing data", missing);
