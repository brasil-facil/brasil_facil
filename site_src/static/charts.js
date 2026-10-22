// Brasil Fácil: draws every indicator chart from its JSON file.
// Style rules come from docs/design/visual-identity.html ("Chart style").

(function () {
  "use strict";

  // Read a colour token from style.css, so the chart always matches the page,
  // in light and dark mode.
  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // "2026-09" -> "2026-10" (the first month after a band ends).
  function nextMonth(period) {
    var parts = period.split("-");
    var year = Number(parts[0]);
    var month = Number(parts[1]) + 1;
    if (month === 13) { year += 1; month = 1; }
    return year + "-" + String(month).padStart(2, "0");
  }

  // "2026-09" -> "2026-09-01"; a yearly "2025" -> "2025-01-01".
  function toDate(period) {
    return period.length === 4 ? period + "-01-01" : period + "-01";
  }

  // One soft rectangle per band: green inside the target, yellow just outside.
  function bandAreas(data, colors) {
    var areas = [];
    data.bands.forEach(function (band) {
      var start = toDate(band.from);
      var end = toDate(nextMonth(band.to));
      function area(low, high, color) {
        areas.push([
          { xAxis: start, yAxis: low, itemStyle: { color: color } },
          { xAxis: end, yAxis: high }
        ]);
      }
      area(band.lower, band.upper, colors.good);
      area(band.lower - data.margin, band.lower, colors.watch);
      area(band.upper, band.upper + data.margin, colors.watch);
    });
    return areas;
  }

  // One dash pattern per comparison country, so lines differ without colour.
  var DASHES = [[6, 3], [2, 3], [10, 3, 2, 3], [4, 2]];
  var MAX_PEERS = 3;

  // Below this width (a phone) the chart switches to its narrow layout:
  // shorter names and shorter numbers at the end of each line.
  var NARROW_PX = 500;

  // An end label: "Economias avançadas US$ 63.876" on a wide screen,
  // "Avançadas 63,9 mil" on a narrow one. The name always comes first: it says
  // which line is which. With no name (a single line), just the value.
  function endText(name, shortName, value, fmt, narrow) {
    var number = narrow ? fmt.short(value) : fmt.value(value);
    var label = narrow ? shortName : name;
    return label ? label + " " + number : number;
  }

  // Room on the right for the end labels: about 6.5 px per character of the
  // longest label, between 64 and 230 px.
  function labelRoom(data, fmt, narrow) {
    var latest = data.points[data.points.length - 1][1];
    var labels = [endText("Brasil", "Brasil", latest, fmt, narrow)];
    data.peers.forEach(function (peer) {
      labels.push(endText(peer.name, peer.short_name, peer.latest.value, fmt, narrow));
    });
    if (data.compare && data.compare.latest !== null) {
      labels.push(endText(data.compare.label, data.compare.label, data.compare.latest, fmt, narrow));
    }
    var longest = Math.max.apply(null, labels.map(function (label) { return label.length; }));
    return Math.min(230, Math.max(64, Math.round(longest * 6.5) + 16));
  }

  // Bar charts name their lines in a legend above the chart instead of at the
  // end of each line: the forecast bars sit where those labels would go.
  // Returns the legend and the height it needs, guessing how many rows it wraps to.
  function topLegend(names, width, colors) {
    var rowWidth = 0;
    var rows = 1;
    names.forEach(function (name) {
      var itemWidth = 18 + 5 + name.length * 6.5 + 14;   // sample + gap + text + space
      if (rowWidth + itemWidth > width && rowWidth > 0) { rows += 1; rowWidth = 0; }
      rowWidth += itemWidth;
    });
    return {
      height: rows * 22,
      legend: {
        data: names,
        top: 0,
        left: 0,
        selectedMode: false,          // clicking a name does nothing
        itemWidth: 18,
        itemHeight: 10,
        itemGap: 14,
        textStyle: { color: colors.muted, fontSize: 12 }
      }
    };
  }

  function buildOption(data, colors, fmt, active, narrow, width) {
    var points = data.points.map(function (p) { return [toDate(p[0]), p[1]]; });
    var last = points[points.length - 1];
    var isBar = data.chart.kind === "bar";
    var list = isBar
      ? barSeries(data, colors, points, active, narrow)
      : series(data, colors, fmt, points, last, active, narrow);
    var legend = isBar
      ? topLegend(list.filter(function (s) { return s.inLegend; })
          .map(function (s) { return s.name; }), width, colors)
      : null;

    return {
      animation: false,
      textStyle: { fontFamily: "Inclusive Sans, Verdana, sans-serif", color: colors.muted },
      legend: legend ? legend.legend : { show: false },
      grid: {
        left: 8,
        right: isBar ? 16 : labelRoom(data, fmt, narrow),
        top: legend ? legend.height + 12 : 16,
        bottom: 8,
        containLabel: true
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: colors.surface,
        borderColor: colors.line,
        textStyle: { color: colors.fg },
        formatter: function (items) {
          var shown = items.filter(function (item) { return item.seriesName && item.value; });
          if (!shown.length) { return ""; }
          return fmt.month(shown[0].value[0]) + shown.map(function (item) {
            return "<br>" + item.seriesName + ": <b>" + fmt.value(item.value[1]) + "</b>";
          }).join("");
        }
      },
      xAxis: {
        type: "time",
        splitNumber: narrow ? 4 : 5,      // fewer year labels on a phone, so they don't touch
        axisLine: { lineStyle: { color: colors.line } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: colors.muted, hideOverlap: true }
      },
      yAxis: {
        type: "value",
        scale: !isBar,        // bars always start from zero

        splitNumber: 4,
        axisLabel: {
          color: colors.muted,
          // Narrow: "60 mil" instead of "US$ 60.000" (the subtitle names the unit).
          formatter: function (v) { return narrow ? fmt.short(v) : fmt.value(v); }
        },
        splitLine: { lineStyle: { color: colors.line } }
      },
      // "inside" zoom with every mouse gesture turned off: only the period
      // buttons move the window. filterMode "filter" lets the y axis rescale.
      dataZoom: [{
        type: "inside",
        filterMode: "filter",
        zoomOnMouseWheel: false,
        moveOnMouseMove: false,
        moveOnMouseWheel: false
      }],
      series: list
    };
  }

  // The bar chart (yearly growth): one bar per year in its zone colour, the
  // IMF forecast as hollow dashed bars, what was expected in January as
  // hollow circles, and the comparison countries as thin grey lines.
  function barSeries(data, colors, points, active, narrow) {
    var pt = data.lang === "pt";
    var zoneColor = { green: colors.goodSolid, yellow: colors.watchSolid, red: colors.bad };
    var list = [];

    var peerIndex = 0;
    data.peers.forEach(function (peer) {
      var isReference = peer.role === "reference";
      var dash = isReference ? "solid" : DASHES[peerIndex++ % DASHES.length];
      if (!isReference && !active.has(peer.geo)) { return; }
      list.push({
        name: peer.name,
        inLegend: true,
        type: "line",
        z: 3,
        data: peer.points.map(function (p) { return [toDate(p[0]), p[1]]; }),
        showSymbol: false,
        lineStyle: { width: 1.5, color: isReference ? colors.compare : colors.peer, type: dash },
        itemStyle: { color: isReference ? colors.compare : colors.peer }
      });
    });

    list.push({
      name: pt ? "Brasil" : "Brazil",
      type: "bar",
      barMaxWidth: 18,
      barGap: "-100%",            // forecast bars share the same slot, not side by side
      data: points.map(function (point, i) {
        var zone = data.point_zones[i];
        return { value: point, itemStyle: { color: zoneColor[zone] || colors.brand } };
      })
    });

    if (data.forecast && data.forecast.length) {
      list.push({
        name: pt ? "Previsão do FMI" : "IMF forecast",
        inLegend: true,
        type: "bar",
        barMaxWidth: 18,
        barGap: "-100%",
        data: data.forecast.map(function (p) { return [toDate(p[0]), p[1]]; }),
        itemStyle: { color: "transparent", borderColor: colors.muted, borderWidth: 1.5, borderType: "dashed" }
      });
    }

    if (data.expected && data.expected.length) {
      list.push({
        name: pt ? "Esperado em janeiro" : "Expected in January",
        inLegend: true,
        type: "scatter",
        z: 4,
        symbol: "circle",
        symbolSize: narrow ? 5 : 8,   // thin bars on a phone: smaller circles
        data: data.expected.map(function (p) { return [toDate(p[0]), p[1]]; }),
        itemStyle: { color: colors.surfaceSolid, borderColor: colors.fg, borderWidth: 1.5 }
      });
    }
    return list;
  }

  function series(data, colors, fmt, points, last, active, narrow) {
    var list = [];
    var brazil = data.lang === "pt" ? "Brasil" : "Brazil";

    // Comparison countries: thin grey lines, labelled at their end. The OECD
    // average (reference) is solid and always on; the others are dashed.
    var peerIndex = 0;
    data.peers.forEach(function (peer) {
      var isReference = peer.role === "reference";
      var dash = isReference ? "solid" : DASHES[peerIndex++ % DASHES.length];
      if (!isReference && !active.has(peer.geo)) { return; }
      list.push({
        name: peer.name,
        type: "line",
        data: peer.points.map(function (p) { return [toDate(p[0]), p[1]]; }),
        showSymbol: false,
        lineStyle: { width: 1.5, color: isReference ? colors.compare : colors.peer, type: dash },
        itemStyle: { color: isReference ? colors.compare : colors.peer },
        endLabel: {
          show: true,
          color: colors.muted,
          formatter: function (p) { return endText(peer.name, peer.short_name, p.value[1], fmt, narrow); }
        },
        labelLayout: { moveOverlap: "shiftY" }
      });
    });

    // A comparison (e.g. IPCA next to INPC): thin grey line, drawn first so
    // Brazil's purple line stays on top. Labelled with its name at the end.
    if (data.compare) {
      list.push({
        name: data.compare.label,
        type: "line",
        data: data.compare.points.map(function (p) { return [toDate(p[0]), p[1]]; }),
        showSymbol: false,
        lineStyle: { width: 1.5, color: colors.compare },
        itemStyle: { color: colors.compare },
        endLabel: {
          show: true,
          color: colors.muted,
          formatter: function (p) {
            return endText(data.compare.label, data.compare.label, p.value[1], fmt, narrow);
          }
        },
        labelLayout: { moveOverlap: "shiftY" }
      });
    }

    list.push({
      name: data.peers.length ? brazil : data.title,
      type: "line",
      data: points,
      showSymbol: false,
      lineStyle: { width: 3, color: colors.brand },
      itemStyle: { color: colors.brand },
      markArea: { silent: true, data: bandAreas(data, colors) },
      endLabel: {
        show: true,
        color: colors.brand,
        fontWeight: 700,
        formatter: function (p) {
          var name = data.peers.length ? brazil : "";
          return endText(name, name, p.value[1], fmt, narrow);
        }
      },
      labelLayout: { moveOverlap: "shiftY" }
    });

    // The dot on the latest value.
    list.push({
      type: "scatter",
      data: [last],
      symbolSize: 9,
      itemStyle: { color: colors.brand },
      tooltip: { show: false },
      silent: true
    });
    return list;
  }

  function setWindow(chart, data, years) {
    var first = toDate(data.points[0][0]);
    var lastPeriod = data.points[data.points.length - 1][0];
    var start = first;
    if (years !== "all") {
      var d = new Date(toDate(lastPeriod));
      d.setFullYear(d.getFullYear() - Number(years));
      start = d.toISOString().slice(0, 10);
    }
    // A forecast reaches past the last result: keep its years in view.
    var forecast = data.forecast && data.forecast.length ? data.forecast : null;
    var end = forecast ? forecast[forecast.length - 1][0] : lastPeriod;
    chart.dispatchAction({ type: "dataZoom", startValue: start, endValue: toDate(end) });
  }

  function setupButtons(box, chart, data) {
    var buttons = box.querySelectorAll(".periods button");
    var firstYear = Number(data.points[0][0].slice(0, 4));
    var lastYear = Number(data.points[data.points.length - 1][0].slice(0, 4));
    var spanYears = lastYear - firstYear;

    buttons.forEach(function (button) {
      var years = button.dataset.years;
      // A window as long as the whole series adds nothing: hide it.
      if (years !== "all" && Number(years) >= spanYears) { button.hidden = true; }
      button.addEventListener("click", function () {
        buttons.forEach(function (b) { b.setAttribute("aria-pressed", String(b === button)); });
        setWindow(chart, data, years);
      });
    });
  }

  // If the default window is hidden (a short series), start on "all" instead.
  function pressVisibleDefault(box) {
    var pressed = box.querySelector('.periods button[aria-pressed="true"]');
    if (pressed && pressed.hidden) {
      pressed.setAttribute("aria-pressed", "false");
      box.querySelector('.periods button[data-years="all"]').setAttribute("aria-pressed", "true");
    }
  }

  function setupPeerButtons(box, active, render) {
    var buttons = box.querySelectorAll(".compare-peers button");
    function refresh() {
      buttons.forEach(function (button) {
        var on = active.has(button.dataset.geo);
        button.setAttribute("aria-pressed", String(on));
        button.disabled = !on && active.size >= MAX_PEERS;
      });
    }
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var geo = button.dataset.geo;
        if (active.has(geo)) { active.delete(geo); } else if (active.size < MAX_PEERS) { active.add(geo); }
        refresh();
        render();
      });
    });
    refresh();
  }

  function currentYears(box) {
    var pressed = box.querySelector('.periods button[aria-pressed="true"]:not([hidden])');
    return pressed ? pressed.dataset.years : "all";
  }

  function draw(el) {
    fetch(el.dataset.src)
      .then(function (response) { return response.json(); })
      .then(function (data) {
        var box = el.closest(".chartbox");
        var locale = data.lang === "pt" ? "pt-BR" : "en-GB";
        var numberFormat = new Intl.NumberFormat(locale, { maximumFractionDigits: data.unit_prefix ? 0 : 2 });
        var monthFormat = new Intl.DateTimeFormat(locale, { month: "short", year: "numeric", timeZone: "UTC" });
        // "compact" writes 60000 as "60 mil" (pt) or "60K" (en).
        var compactFormat = new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 });
        var fmt = {
          number: function (v) { return numberFormat.format(v); },
          // A value with its unit: "4,58%" or "US$ 19.968".
          value: function (v) { return data.unit_prefix + numberFormat.format(v) + data.unit; },
          // On a phone: money as "63,9 mil" (no "US$ "); percentages stay "4,58%".
          short: function (v) {
            return data.unit_prefix ? compactFormat.format(v) : fmt.value(v);
          },
          month: function (date) {
            return data.period_kind === "year" ? date.slice(0, 4) : monthFormat.format(new Date(date));
          }
        };

        var chart = echarts.init(el, null, { renderer: "svg" });

        function render() {
          var colors = {
            brand: token("--brand"), fg: token("--fg"), muted: token("--muted"),
            line: token("--line"), surface: token("--surface"),
            good: token("--good-band"), watch: token("--watch-band"), compare: token("--cmp-line"),
            peer: token("--cmp-peer"),
            // Solid colours for bars (the "band" ones above are see-through).
            goodSolid: token("--good"), watchSolid: token("--watch-bar"), bad: token("--bad"),
            surfaceSolid: token("--surface")
          };
          // Measure the chart's own box, not the window: that's the space we have.
          var width = el.clientWidth;
          chart.setOption(buildOption(data, colors, fmt, active, width < NARROW_PX, width), true);
          setWindow(chart, data, currentYears(box));
        }

        // The comparison countries switched on, starting with the default ones.
        var active = new Set(data.peers.filter(function (p) {
          return p.role === "peer" && p.default_on;
        }).map(function (p) { return p.geo; }));

        setupButtons(box, chart, data);
        pressVisibleDefault(box);
        setupPeerButtons(box, active, render);
        render();
        // On resize (a phone turned sideways), redraw: the layout may change.
        window.addEventListener("resize", function () { chart.resize(); render(); });
        // theme.js sends "themechange" when the look switches (button or device).
        document.addEventListener("themechange", render);
      });
  }

  document.querySelectorAll(".chart[data-src]").forEach(draw);
})();
