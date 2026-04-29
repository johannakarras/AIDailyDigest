const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];
const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function isWeekKey(key) {
  return /^\d{4}-W\d{2}$/.test(key);
}

// Returns the Monday Date of an ISO week key like "2026-W18"
function weekKeyToMonday(weekKey) {
  const [yearStr, weekStr] = weekKey.split("-W");
  const year = parseInt(yearStr, 10);
  const week = parseInt(weekStr, 10);
  // Jan 4 is always in ISO week 1
  const jan4 = new Date(year, 0, 4);
  const dayOfWeek = (jan4.getDay() + 6) % 7; // 0=Mon … 6=Sun
  const monday = new Date(jan4);
  monday.setDate(jan4.getDate() - dayOfWeek + (week - 1) * 7);
  return monday;
}

function formatWeekLabel(weekKey) {
  const mon = weekKeyToMonday(weekKey);
  const fri = new Date(mon);
  fri.setDate(mon.getDate() + 4);
  if (mon.getMonth() === fri.getMonth()) {
    return `${MONTH_SHORT[mon.getMonth()]} ${mon.getDate()}–${fri.getDate()}`;
  }
  return `${MONTH_SHORT[mon.getMonth()]} ${mon.getDate()}–${MONTH_SHORT[fri.getMonth()]} ${fri.getDate()}`;
}

function formatWeekHeading(weekKey) {
  const mon = weekKeyToMonday(weekKey);
  const fri = new Date(mon);
  fri.setDate(mon.getDate() + 4);
  if (mon.getMonth() === fri.getMonth()) {
    return `${MONTH_NAMES[mon.getMonth()]} ${mon.getDate()}–${fri.getDate()}, ${mon.getFullYear()}`;
  }
  return `${MONTH_NAMES[mon.getMonth()]} ${mon.getDate()}–${MONTH_NAMES[fri.getMonth()]} ${fri.getDate()}, ${mon.getFullYear()}`;
}

function formatDate(dateKey) {
  const [year, month, day] = dateKey.split("-").map(Number);
  return `${MONTH_NAMES[month - 1]} ${day}, ${year}`;
}

// Returns {year, month (0-padded string), displayLabel} for any key type
function keyMeta(key) {
  if (isWeekKey(key)) {
    const m = weekKeyToMonday(key);
    return {
      year: String(m.getFullYear()),
      month: String(m.getMonth() + 1).padStart(2, "0"),
      label: formatWeekLabel(key),
    };
  }
  const [year, month, day] = key.split("-");
  return { year, month, label: formatDate(key) };
}

function buildSidebar(digests) {
  const sidebar = document.getElementById("sidebar");
  const allKeys = Object.keys(digests).sort().reverse();

  if (allKeys.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No digests yet.";
    sidebar.appendChild(empty);
    return;
  }

  const byYear = {};
  for (const key of allKeys) {
    const { year, month, label } = keyMeta(key);
    if (!byYear[year]) byYear[year] = {};
    if (!byYear[year][month]) byYear[year][month] = [];
    byYear[year][month].push({ key, label });
  }

  const years = Object.keys(byYear).sort().reverse();
  const mostRecentYear = years[0];

  for (const year of years) {
    const yearDetails = document.createElement("details");
    yearDetails.className = "year-node";
    if (year === mostRecentYear) yearDetails.open = true;

    const yearSummary = document.createElement("summary");
    yearSummary.textContent = year;
    yearDetails.appendChild(yearSummary);

    const months = Object.keys(byYear[year]).sort().reverse();
    const mostRecentMonth = months[0];

    for (const month of months) {
      const monthDetails = document.createElement("details");
      monthDetails.className = "month-node";
      if (year === mostRecentYear && month === mostRecentMonth) {
        monthDetails.open = true;
      }

      const monthSummary = document.createElement("summary");
      monthSummary.textContent = MONTH_NAMES[Number(month) - 1];
      monthDetails.appendChild(monthSummary);

      for (const { key, label } of byYear[year][month]) {
        const span = document.createElement("span");
        span.className = "day-link";
        span.dataset.date = key;
        span.textContent = label;
        span.addEventListener("click", () => selectDate(key));
        monthDetails.appendChild(span);
      }

      yearDetails.appendChild(monthDetails);
    }

    sidebar.appendChild(yearDetails);
  }
}

function selectDate(dateKey) {
  document.querySelectorAll(".day-link").forEach(el => {
    el.classList.toggle("active", el.dataset.date === dateKey);
  });
  renderDigest(dateKey);
}

function renderDigest(dateKey) {
  const dateHeading = document.getElementById("date-heading");
  dateHeading.textContent = isWeekKey(dateKey) ? formatWeekHeading(dateKey) : formatDate(dateKey);

  const cardsContainer = document.getElementById("cards-container");
  cardsContainer.innerHTML = "";

  const rawPapers = DIGESTS[dateKey];
  if (!rawPapers || rawPapers.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No papers in this digest.";
    cardsContainer.appendChild(empty);
    return;
  }

  const papers = rawPapers.slice().sort((a, b) => (b.stars || 0) - (a.stars || 0));

  for (const paper of papers) {
    const card = document.createElement("div");
    card.className = "paper-card";

    const details = document.createElement("details");

    // --- Summary (always visible) ---
    const summary = document.createElement("summary");

    const summaryLeft = document.createElement("div");
    summaryLeft.className = "paper-summary-left";

    const titleRow = document.createElement("div");
    titleRow.className = "paper-title-row";

    const titleEl = document.createElement("p");
    titleEl.className = "paper-title";
    const link = document.createElement("a");
    link.href = paper.url || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = paper.title || "(no title)";
    link.addEventListener("click", e => e.stopPropagation());
    titleEl.appendChild(link);
    titleRow.appendChild(titleEl);

    if (paper.stars) {
      const starsEl = document.createElement("span");
      starsEl.className = "paper-stars";
      starsEl.title = paper.rating_rationale || "";
      starsEl.textContent = "⭐".repeat(paper.stars);
      titleRow.appendChild(starsEl);
    }

    summaryLeft.appendChild(titleRow);

    if (paper.authors && paper.authors.length) {
      const authorsEl = document.createElement("p");
      authorsEl.className = "paper-authors";
      authorsEl.textContent = paper.authors.join(", ");
      summaryLeft.appendChild(authorsEl);
    }

    if (paper.affiliations && paper.affiliations.length) {
      const affEl = document.createElement("p");
      affEl.className = "paper-affiliations";
      affEl.textContent = paper.affiliations.join(", ");
      summaryLeft.appendChild(affEl);
    }

    summary.appendChild(summaryLeft);

    const arrow = document.createElement("span");
    arrow.className = "paper-toggle-icon";
    arrow.textContent = "▼";
    summary.appendChild(arrow);

    details.appendChild(summary);

    // --- Body (shown when expanded) ---
    const body = document.createElement("div");
    body.className = "paper-body";

    const meta = document.createElement("p");
    meta.className = "paper-meta";
    const metaParts = [];
    if (paper.date) metaParts.push(paper.date);
    if (paper.source) metaParts.push(`via ${paper.source}`);
    meta.textContent = metaParts.join(" · ");
    body.appendChild(meta);

    const fields = [
      { label: "What it does", key: "description" },
      { label: "Novel contribution", key: "contribution" },
      { label: "Limitations", key: "limitations" },
    ];

    for (const { label, key } of fields) {
      if (!paper[key]) continue;
      const labelEl = document.createElement("p");
      labelEl.className = "field-label";
      labelEl.textContent = label;
      body.appendChild(labelEl);

      const valueEl = document.createElement("p");
      valueEl.className = "field-value";
      valueEl.textContent = paper[key];
      body.appendChild(valueEl);
    }

    if (paper.links && paper.links.length) {
      const labelEl = document.createElement("p");
      labelEl.className = "field-label";
      labelEl.textContent = "Links";
      body.appendChild(labelEl);

      const linksEl = document.createElement("div");
      linksEl.className = "paper-links";
      for (const { label, url } of paper.links) {
        const a = document.createElement("a");
        a.className = "paper-link";
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = label;
        linksEl.appendChild(a);
      }
      body.appendChild(linksEl);
    }

    details.appendChild(body);
    card.appendChild(details);
    cardsContainer.appendChild(card);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  buildSidebar(DIGESTS);
  const mostRecent = Object.keys(DIGESTS).sort().reverse()[0];
  if (mostRecent) selectDate(mostRecent);
});
