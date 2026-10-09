/* Values are transcribed from the supplied paper's Appendix D, not estimated from images. */
(() => {
  "use strict";
  const svgNS = "http://www.w3.org/2000/svg";
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const svgElement = (tag, attributes, text) => {
    const node = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const percent = value => `${value.toFixed(1)}%`;

  function mountChart(figure, config, policies) {
    const selected = new Set(policies.map(policy => policy.id));
    const widget = element("div", "results-chart");
    const scroll = element("div", "chart-scroll");
    const legend = element("div", "chart-legend");
    legend.setAttribute("role", "group");
    legend.setAttribute("aria-label", `${config.title}: visible policies`);
    const tooltip = element("div", "chart-tooltip");
    tooltip.hidden = true;
    tooltip.id = `${figure.dataset.resultsChart}-tooltip`;
    tooltip.setAttribute("role", "tooltip");
    const hint = element("p", "chart-hint", "Hover, tap, or focus a bar for details. Toggle policies using the legend.");
    const mobileHint = element("span", "chart-mobile-hint", " Swipe horizontally to view the full chart.");
    hint.append(mobileHint);
    const details = element("details", "chart-data");
    details.append(element("summary", "", `View numerical data · ${config.source}`));
    const tableScroll = element("div", "chart-table-scroll");
    const table = element("table");
    table.append(element("caption", "", `All policies; values as reported in the paper, ${config.source}.`));
    const head = element("thead");
    const header = element("tr");
    for (const title of ["Task / condition", "Policy", "Instructions", "Successes / trials", "Success", "Wilson 95% CI"]) {
      const cell = element("th", "", title);
      cell.scope = "col";
      header.append(cell);
    }
    head.append(header);
    table.append(head);
    const body = element("tbody");
    for (const group of config.groups) for (const policy of policies) for (const variant of config.variants) {
      const [successes, trials, rate, lower, upper] = group.series[policy.id][variant.id];
      const row = element("tr");
      for (const text of [group.label.join(" "), policy.label, variant.label || group.condition,
        `${successes} / ${trials}`, percent(rate), `${percent(lower)}–${percent(upper)}`]) row.append(element("td", "", text));
      body.append(row);
    }
    table.append(body);
    tableScroll.append(table);
    details.append(tableScroll);
    widget.append(scroll, legend);
    if (config.variants.length > 1) {
      const variantLegend = element("div", "chart-variants");
      for (const variant of config.variants) {
        const key = element("span");
        const swatch = element("i", `chart-variant-swatch ${variant.tone}`);
        swatch.setAttribute("aria-hidden", "true");
        key.append(swatch, document.createTextNode(variant.label));
        variantLegend.append(key);
      }
      widget.append(variantLegend);
    }
    widget.append(hint, tooltip, details);
    let pinned = null;
    let active = null;

    function hideTooltip() {
      if (active) {
        active.classList.remove("is-selected");
        active.removeAttribute("aria-describedby");
      }
      active = null;
      tooltip.hidden = true;
    }

    function showTooltip(target, group, policy, variant, values) {
      if (active && active !== target) {
        active.classList.remove("is-selected");
        active.removeAttribute("aria-describedby");
      }
      active = target;
      active.classList.add("is-selected");
      active.setAttribute("aria-describedby", tooltip.id);
      const [successes, trials, rate, lower, upper] = values;
      const policyRow = element("div", "tooltip-policy");
      const swatch = element("span", "chart-swatch");
      swatch.style.backgroundColor = policy.color;
      policyRow.append(swatch, document.createTextNode(policy.label));
      const condition = config.variants.length === 1 ? group.condition
        : [group.condition, variant.label].filter(Boolean).join(" · ");
      tooltip.replaceChildren(element("strong", "", group.label.join(" ")), policyRow,
        element("div", "tooltip-condition", condition), element("div", "tooltip-rate", percent(rate)),
        element("div", "", `${successes} successes / ${trials} trials`),
        element("div", "", `Wilson 95% CI: ${percent(lower)}–${percent(upper)}`),
        element("div", "tooltip-source", `Paper ${variant.source || config.source}`));
      tooltip.hidden = false;
      const box = target.getBoundingClientRect();
      const parent = widget.getBoundingClientRect();
      const left = Math.min(Math.max(8, box.left - parent.left + box.width / 2 - tooltip.offsetWidth / 2), parent.width - tooltip.offsetWidth - 8);
      const preferredTop = box.top - parent.top - tooltip.offsetHeight - 10;
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${preferredTop >= 0 ? preferredTop : Math.max(8, box.top - parent.top + 28)}px`;
    }

    function render() {
      pinned = null;
      hideTooltip();
      const shownPolicies = policies.filter(policy => selected.has(policy.id));
      const width = 900, height = 384, left = 58, right = 16, top = 38, bottom = 326;
      const plotWidth = width - left - right;
      const y = value => bottom - value / 100 * (bottom - top);
      const svg = svgElement("svg", {viewBox: `0 0 ${width} ${height}`, class: "chart-svg", role: "group", "aria-label": `${config.title}. Success rate, 0 to 100 percent, with Wilson 95% confidence intervals.`});
      svg.style.minWidth = `${config.minWidth}px`;
      svg.append(svgElement("text", {x: left, y: 20, class: "chart-axis"}, "Success (%)"));
      for (let tick = 0; tick <= 100; tick += 20) {
        svg.append(svgElement("line", {x1: left, x2: width-right, y1: y(tick), y2: y(tick), class: tick === 0 ? "chart-baseline" : "chart-grid", "aria-hidden": "true"}));
        svg.append(svgElement("text", {x: left-10, y: y(tick)+4, "text-anchor": "end", class: "chart-axis"}, `${tick}%`));
      }
      const groupWidth = plotWidth / config.groups.length;
      config.groups.forEach((group, groupIndex) => {
        const barCount = shownPolicies.length * config.variants.length;
        const gap = 4;
        const policyGap = config.variants.length > 1 ? 5 : 0;
        const gaps = Math.max(0, barCount-1)*gap + Math.max(0, shownPolicies.length-1)*policyGap;
        const barWidth = Math.min(34, (groupWidth - 24 - gaps) / Math.max(1, barCount));
        const allBarsWidth = barCount*barWidth + gaps;
        const center = left + groupWidth*(groupIndex+.5);
        let x = center - allBarsWidth/2;
        for (const policy of shownPolicies) {
          for (const variant of config.variants) {
            const values = group.series[policy.id][variant.id];
            const [successes, trials, rate, lower, upper] = values;
            const condition = config.variants.length === 1 ? group.condition : [group.condition, variant.label].filter(Boolean).join(" · ");
            const bar = svgElement("g", {class: "chart-bar", role: "button", tabindex: 0,
              "aria-label": `${group.label.join(" ")}, ${policy.label}, ${condition}: ${percent(rate)}, ${successes} successes in ${trials} trials, Wilson 95% confidence interval ${percent(lower)} to ${percent(upper)}`,
              "data-policy": policy.id, "data-variant": variant.id, "data-successes": successes, "data-trials": trials, "data-rate": rate});
            // A full-height hit target keeps zero-success bars inspectable too.
            bar.append(svgElement("rect", {x: x-2, y: top, width: barWidth+4, height: bottom-top, fill: "transparent", class: "bar-hit"}));
            bar.append(svgElement("rect", {x, y: y(rate), width: barWidth, height: Math.max(1.5, bottom-y(rate)), fill: variant.tone === "light" ? policy.light : policy.color, class: "bar-fill"}));
            const middle = x + barWidth/2;
            bar.append(svgElement("line", {x1: middle, x2: middle, y1: y(lower), y2: y(upper), class: "chart-whisker"}));
            for (const bound of [lower, upper]) bar.append(svgElement("line", {x1: middle-4, x2: middle+4, y1: y(bound), y2: y(bound), class: "chart-whisker"}));
            const show = () => showTooltip(bar, group, policy, variant, values);
            bar.addEventListener("pointerenter", event => { if (event.pointerType !== "touch" && !pinned) show(); });
            bar.addEventListener("pointerleave", () => { if (!pinned) hideTooltip(); });
            bar.addEventListener("focus", () => { pinned = null; show(); });
            bar.addEventListener("blur", () => { if (!pinned) hideTooltip(); });
            const toggle = () => {
              if (pinned === bar) { pinned = null; hideTooltip(); }
              else { pinned = bar; show(); }
            };
            bar.addEventListener("click", toggle);
            bar.addEventListener("keydown", event => {
              if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
              if (event.key === "Escape") { pinned = null; hideTooltip(); }
            });
            svg.append(bar);
            x += barWidth + gap;
          }
          x += policyGap;
        }
        group.label.forEach((line, lineIndex) => svg.append(svgElement("text", {x: center, y: bottom+27+lineIndex*18, "text-anchor": "middle", class: "chart-label"}, line)));
      });
      if (!shownPolicies.length) svg.append(svgElement("text", {x: left+plotWidth/2, y: 185, "text-anchor": "middle", class: "chart-label"}, "Select a policy below to show results."));
      scroll.replaceChildren(svg);
    }

    for (const policy of policies) {
      const button = element("button", "chart-policy");
      button.type = "button";
      button.setAttribute("aria-pressed", "true");
      const swatch = element("span", "chart-swatch");
      swatch.style.backgroundColor = policy.color;
      swatch.setAttribute("aria-hidden", "true");
      button.append(swatch, document.createTextNode(policy.label));
      button.addEventListener("click", () => {
        if (selected.has(policy.id)) selected.delete(policy.id); else selected.add(policy.id);
        button.setAttribute("aria-pressed", String(selected.has(policy.id)));
        render();
      });
      legend.append(button);
    }
    widget.addEventListener("keydown", event => { if (event.key === "Escape") { pinned = null; hideTooltip(); } });
    document.addEventListener("pointerdown", event => { if (!widget.contains(event.target)) { pinned = null; hideTooltip(); } });
    scroll.addEventListener("scroll", () => { pinned = null; hideTooltip(); }, {passive: true});
    window.addEventListener("resize", () => { pinned = null; hideTooltip(); }, {passive: true});
    render();
    figure.prepend(widget);
    figure.querySelector(".chart-fallback").hidden = true;
  }

  fetch("assets/results-chart-data.json")
    .then(response => { if (!response.ok) throw new Error("Chart data unavailable"); return response.json(); })
    .then(data => {
      for (const figure of document.querySelectorAll("[data-results-chart]")) {
        mountChart(figure, data.charts[figure.dataset.resultsChart], data.policies);
      }
    })
    // Retain the original paper figure if data or scripting is unavailable.
    .catch(error => console.warn("Using static Spa-Bench charts:", error));
})();
