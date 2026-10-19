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

  function toDate(period) {
    return period + "-01";
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

  function buildOption(data, colors, fmt) {
    var points = data.points.map(function (p) { return [toDate(p[0]), p[1]]; });
    var last = points[points.length - 1];

    return {
      animation: false,
      textStyle: { fontFamily: "Inclusive Sans, Verdana, sans-serif", color: colors.muted },
      grid: { left: 8, right: 64, top: 16, bottom: 8, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: colors.surface,
        borderColor: colors.line,
        textStyle: { color: colors.fg },
        formatter: function (items) {
          var item = items[0];
          return fmt.month(item.value[0]) + "<br><b>" + fmt.number(item.value[1]) + data.unit + "</b>";
        }
      },
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: colors.line } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { color: colors.muted, hideOverlap: true }
      },
      yAxis: {
        type: "value",
        scale: true,
        splitNumber: 4,
        axisLabel: {
          color: colors.muted,
          formatter: function (v) { return fmt.number(v) + data.unit; }
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
      series: [
        {
          name: data.title,
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
            formatter: function (p) { return fmt.number(p.value[1]) + data.unit; }
          }
        },
        {
          // The dot on the latest value.
          type: "scatter",
          data: [last],
          symbolSize: 9,
          itemStyle: { color: colors.brand },
          tooltip: { show: false },
          silent: true
        }
      ]
    };
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
    chart.dispatchAction({ type: "dataZoom", startValue: start, endValue: toDate(lastPeriod) });
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
        var numberFormat = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
        var monthFormat = new Intl.DateTimeFormat(locale, { month: "short", year: "numeric", timeZone: "UTC" });
        var fmt = {
          number: function (v) { return numberFormat.format(v); },
          month: function (date) { return monthFormat.format(new Date(date)); }
        };

        var chart = echarts.init(el, null, { renderer: "svg" });

        function render() {
          var colors = {
            brand: token("--brand"), fg: token("--fg"), muted: token("--muted"),
            line: token("--line"), surface: token("--surface"),
            good: token("--good-band"), watch: token("--watch-band")
          };
          chart.setOption(buildOption(data, colors, fmt), true);
          setWindow(chart, data, currentYears(box));
        }

        setupButtons(box, chart, data);
        render();
        window.addEventListener("resize", function () { chart.resize(); });
        // theme.js sends "themechange" when the look switches (button or device).
        document.addEventListener("themechange", render);
      });
  }

  document.querySelectorAll(".chart[data-src]").forEach(draw);
})();
