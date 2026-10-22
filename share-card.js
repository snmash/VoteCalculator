/* votepower.us share images.
 * drawShareCard(canvas, data, format) paints the sticker card onto a canvas.
 *   format "story": 1080x1350 (Instagram 4:5) image people download or share.
 *   format "og":    1200x630 link-preview image (Open Graph / X cards).
 * data: { lead, number, place, election, turnout }
 *   lead      "I'M VOTING FOR" (or "MY VOTE COUNTS FOR" after Election Day)
 *   number    "1.8"
 *   place     "King County, WA"
 *   election  "2022 midterm"
 *   turnout   "57%"
 * Fonts must be loaded first: call loadShareFonts() and await it.
 */
(function (global) {
  var INK = "#22163A";
  var STICKER = "#FFD23F";
  var POP = "#FF8A3D";
  var VIOLET = "#B9A9FF";
  var WHITE = "#FFFFFF";
  var SOFT = "#D9D2F5";
  var DISPLAY = "'Bricolage Grotesque', 'Archivo', system-ui, sans-serif";

  function loadShareFonts() {
    if (!document.fonts || !document.fonts.load) return Promise.resolve();
    return Promise.all([
      document.fonts.load("800 64px 'Bricolage Grotesque'"),
      document.fonts.load("800 64px 'Archivo'")
    ]).catch(function () {});
  }

  function star(ctx, cx, cy, r, color) {
    ctx.save();
    ctx.fillStyle = color;
    ctx.beginPath();
    for (var i = 0; i < 10; i++) {
      var ang = -Math.PI / 2 + (i * Math.PI) / 5;
      var rad = i % 2 === 0 ? r : r * 0.45;
      var x = cx + Math.cos(ang) * rad;
      var y = cy + Math.sin(ang) * rad;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function setSpacing(ctx, px) {
    if ("letterSpacing" in ctx) ctx.letterSpacing = px + "px";
  }

  // Shrink the font until the text fits maxWidth.
  function fitFont(ctx, text, weight, size, maxWidth, family) {
    var s = size;
    ctx.font = weight + " " + s + "px " + (family || DISPLAY);
    while (ctx.measureText(text).width > maxWidth && s > 10) {
      s -= 2;
      ctx.font = weight + " " + s + "px " + (family || DISPLAY);
    }
    return s;
  }

  function sticker(ctx, cx, cy, r, d) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate((-7 * Math.PI) / 180);

    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fillStyle = STICKER;
    ctx.fill();
    ctx.lineWidth = r * 0.027;
    ctx.strokeStyle = WHITE;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(0, 0, r * 0.88, 0, Math.PI * 2);
    ctx.setLineDash([r * 0.06, r * 0.045]);
    ctx.lineWidth = r * 0.013;
    ctx.strokeStyle = INK;
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = INK;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";

    setSpacing(ctx, r * 0.016);
    fitFont(ctx, d.lead, 800, Math.round(r * 0.12), r * 1.45);
    ctx.fillText(d.lead, 0, -r * 0.42);

    setSpacing(ctx, -r * 0.02);
    fitFont(ctx, d.number, 800, Math.round(r * 0.85), r * 1.5);
    ctx.fillText(d.number, 0, r * 0.3);

    setSpacing(ctx, r * 0.02);
    ctx.font = "800 " + Math.round(r * 0.145) + "px " + DISPLAY;
    ctx.fillText("PEOPLE", 0, r * 0.56);
    setSpacing(ctx, 0);

    ctx.restore();
  }

  function drawStory(ctx, W, H, d) {
    ctx.fillStyle = INK;
    ctx.fillRect(0, 0, W, H);
    star(ctx, 150, 300, 60, POP);
    star(ctx, 950, 880, 38, VIOLET);
    star(ctx, 930, 230, 22, STICKER);

    ctx.fillStyle = WHITE;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    var top = d.place + " · " + d.election;
    fitFont(ctx, top, 800, 46, W - 140);
    ctx.fillText(top, W / 2, 128);

    sticker(ctx, W / 2, 625, 370, d);

    ctx.fillStyle = WHITE;
    ctx.textAlign = "center";
    var line = "Only " + d.turnout + " of my county voted.";
    fitFont(ctx, line, 800, 44, W - 160);
    ctx.fillText(line, W / 2, 1150);
    ctx.fillStyle = STICKER;
    fitFont(ctx, "How many are you voting for?", 800, 52, W - 140);
    ctx.fillText("How many are you voting for?", W / 2, 1222);
    ctx.fillStyle = SOFT;
    ctx.font = "800 40px " + DISPLAY;
    ctx.fillText("votepower.us", W / 2, 1290);
  }

  function drawOg(ctx, W, H, d) {
    ctx.fillStyle = INK;
    ctx.fillRect(0, 0, W, H);
    star(ctx, 70, 80, 34, POP);
    star(ctx, 560, 560, 24, VIOLET);
    star(ctx, 1130, 70, 18, STICKER);

    sticker(ctx, 315, 318, 250, d);

    var x = 620;
    var maxW = W - x - 60;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";

    ctx.fillStyle = WHITE;
    fitFont(ctx, d.place, 800, 60, maxW);
    ctx.fillText(d.place, x, 190);

    ctx.fillStyle = SOFT;
    var sub = d.sub || (d.election + " · " + d.turnout + " turnout");
    fitFont(ctx, sub, 800, 34, maxW);
    ctx.fillText(sub, x, 245);

    ctx.fillStyle = STICKER;
    ctx.font = "800 50px " + DISPLAY;
    ctx.fillText("How many people", x, 360);
    ctx.fillText("are you voting for?", x, 420);

    ctx.fillStyle = WHITE;
    ctx.font = "800 36px " + DISPLAY;
    ctx.fillText("votepower.us", x, 530);
  }

  function drawShareCard(canvas, d, format) {
    var W = format === "og" ? 1200 : 1080;
    var H = format === "og" ? 630 : 1350;
    canvas.width = W;
    canvas.height = H;
    var ctx = canvas.getContext("2d");
    if (format === "og") drawOg(ctx, W, H, d); else drawStory(ctx, W, H, d);
    return canvas;
  }

  global.drawShareCard = drawShareCard;
  global.loadShareFonts = loadShareFonts;
})(window);
