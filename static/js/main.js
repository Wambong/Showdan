/* =========================================================
   main.js (rewritten)
   Works with normal full-page loads AND HTMX/partial swaps
   so templates/accounts/dash_pages/profile_edit.html works
   without adding inline JS.

   Strategy:
   - All features are initialized by calling Showdan.init(root)
   - We call it on DOMContentLoaded (full page)
   - We call it on htmx:afterSwap and htmx:load (dynamic swaps)

   Notes:
   - Every initializer MUST be safe to run multiple times.
   - We mark initialized elements using data-* flags.
========================================================= */

(function () {
  "use strict";

  const Showdan = (window.Showdan = window.Showdan || {});

  /* -------------------------
     Small helpers
  ------------------------- */
  function q(root, sel) {
    return (root || document).querySelector(sel);
  }
  function qa(root, sel) {
    return Array.from((root || document).querySelectorAll(sel));
  }
  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  /* -------------------------
     1) Account type -> toggle professions
  ------------------------- */
  function initAccountTypeToggle(root) {
    const accountType = q(root, "#id_account_type");
    const professionsWrapper = q(root, "#professions-wrapper");
    if (!accountType || !professionsWrapper) return;

    if (accountType.dataset.sdBound === "1") return;
    accountType.dataset.sdBound = "1";

    function toggle() {
      professionsWrapper.style.display =
        accountType.value === "professional" ? "block" : "none";
    }

    toggle();
    accountType.addEventListener("change", toggle);
  }

  /* -------------------------
     2) DOB wheel picker
     Requires:
       - hidden input #id_date_of_birth (YYYY-MM-DD)
       - selects: #dob-day, #dob-month, #dob-year
       - output: #dob-output
  ------------------------- */
  function initDobWheel(root) {
    const hiddenDob = q(root, "#id_date_of_birth");
    const daySel = q(root, "#dob-day");
    const monthSel = q(root, "#dob-month");
    const yearSel = q(root, "#dob-year");
    const output = q(root, "#dob-output");

    if (!hiddenDob || !daySel || !monthSel || !yearSel || !output) return;

    // prevent double-binding
    if (hiddenDob.dataset.sdInitDob === "1") return;
    hiddenDob.dataset.sdInitDob = "1";

    function fillSelect(select, start, end, formatter) {
      select.innerHTML = "";
      for (let i = start; i <= end; i++) {
        const opt = document.createElement("option");
        opt.value = String(i);
        opt.textContent = formatter ? formatter(i) : String(i);
        select.appendChild(opt);
      }
    }

    function daysInMonth(year, month) {
      return new Date(year, month, 0).getDate(); // month is 1-12
    }

    function setSelected(select, value) {
      const opts = Array.from(select.options);
      const idx = opts.findIndex((o) => String(o.value) === String(value));
      if (idx >= 0) select.selectedIndex = idx;
    }

    function markActive(select, cls) {
      Array.from(select.options).forEach((opt) => opt.classList.remove(cls));
      const opt = select.options[select.selectedIndex];
      if (opt) opt.classList.add(cls);
    }

    function clampDayToMonth() {
      const y = Number(yearSel.value);
      const m = Number(monthSel.value);
      const maxD = daysInMonth(y, m);

      const currentD = Number(daySel.value || 1);
      fillSelect(daySel, 1, maxD, (n) => pad2(n));
      setSelected(daySel, Math.min(currentD, maxD));
    }

    function syncHidden() {
      const y = Number(yearSel.value);
      const m = Number(monthSel.value);
      const d = Number(daySel.value);

      if (!y || !m || !d) return;

      hiddenDob.value = `${y}-${pad2(m)}-${pad2(d)}`;
      output.textContent = `${pad2(d)}.${pad2(m)}.${y}`;

      markActive(daySel, "dob-active");
      markActive(monthSel, "dob-active");
      markActive(yearSel, "dob-active");

      [daySel, monthSel, yearSel].forEach((sel) => {
        const opt = sel.options[sel.selectedIndex];
        if (opt && typeof opt.scrollIntoView === "function") {
          opt.scrollIntoView({ block: "center" });
        }
      });
    }

    // Build month/year lists once
    fillSelect(monthSel, 1, 12, (n) => pad2(n));

    const now = new Date();
    const thisYear = now.getFullYear();
    const minYear = thisYear - 100;
    const maxYear = thisYear;
    yearSel.innerHTML = "";
    for (let y = maxYear; y >= minYear; y--) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = String(y);
      yearSel.appendChild(opt);
    }

    // Initial value
    const initial = (hiddenDob.value || "").trim();
    if (initial && initial.includes("-")) {
      const parts = initial.split("-").map((x) => parseInt(x, 10));
      const yy = parts[0], mm = parts[1], dd = parts[2];
      if (yy && mm && dd) {
        setSelected(yearSel, yy);
        setSelected(monthSel, mm);
        clampDayToMonth();
        setSelected(daySel, dd);
      } else {
        // fallback default
        setSelected(monthSel, 7);
        setSelected(yearSel, thisYear - 20);
        clampDayToMonth();
        setSelected(daySel, 7);
      }
    } else {
      setSelected(monthSel, 7);
      setSelected(yearSel, thisYear - 20);
      clampDayToMonth();
      setSelected(daySel, 7);
    }

    clampDayToMonth();
    syncHidden();

    yearSel.addEventListener("change", () => {
      clampDayToMonth();
      syncHidden();
    });
    monthSel.addEventListener("change", () => {
      clampDayToMonth();
      syncHidden();
    });
    daySel.addEventListener("change", syncHidden);
  }

  /* -------------------------
     3) Years of experience wheel
     Requires:
       - hidden input #id_years_of_experience
       - select #exp-years
       - output #exp-output
  ------------------------- */
  function initExperienceWheel(root) {
    const hiddenExp = q(root, "#id_years_of_experience");
    const expSel = q(root, "#exp-years");
    const expOut = q(root, "#exp-output");

    if (!hiddenExp || !expSel || !expOut) return;

    if (hiddenExp.dataset.sdInitExp === "1") return;
    hiddenExp.dataset.sdInitExp = "1";

    const maxYears = 60;

    expSel.innerHTML = "";
    for (let y = 0; y <= maxYears; y++) {
      const opt = document.createElement("option");
      opt.value = String(y);
      opt.textContent = pad2(y);
      expSel.appendChild(opt);
    }

    function setSelected(select, value) {
      const opts = Array.from(select.options);
      const idx = opts.findIndex((o) => String(o.value) === String(value));
      if (idx >= 0) select.selectedIndex = idx;
    }

    function markActive(select) {
      Array.from(select.options).forEach((opt) => opt.classList.remove("exp-active"));
      const opt = select.options[select.selectedIndex];
      if (opt) opt.classList.add("exp-active");
    }

    function sync() {
      const val = Number(expSel.value);
      hiddenExp.value = Number.isFinite(val) ? String(val) : "0";
      expOut.textContent = val === 1 ? "1 year" : `${val} years`;
      markActive(expSel);

      const opt = expSel.options[expSel.selectedIndex];
      if (opt && typeof opt.scrollIntoView === "function") {
        opt.scrollIntoView({ block: "center" });
      }
    }

    const initial = hiddenExp.value !== "" ? Number(hiddenExp.value) : 0;
    setSelected(expSel, Number.isFinite(initial) ? initial : 0);
    sync();

    expSel.addEventListener("change", sync);
  }

  /* -------------------------
     4) About me word counter
  ------------------------- */
  function initAboutWordCounter(root) {
    const textarea = q(root, "#id_about_me");
    const counter = q(root, "#about-word-count");
    if (!textarea || !counter) return;

    if (textarea.dataset.sdBound === "1") return;
    textarea.dataset.sdBound = "1";

    const MAX = 1000;

    function countWords(text) {
      const words = (text || "").trim().match(/\S+/g);
      return words ? words.length : 0;
    }

    function update() {
      const n = countWords(textarea.value);
      counter.textContent = String(n);
      if (n > MAX) counter.classList.add("text-danger", "fw-semibold");
      else counter.classList.remove("text-danger", "fw-semibold");
    }

    textarea.addEventListener("input", update);
    update();
  }

  /* -------------------------
     5) Currency sign + show/hide pricing fields
  ------------------------- */
  function initCurrencyPricing(root) {
    const currencySelect = q(root, "#id_currency");
    const pricingFields = q(root, "#pricing-fields");
    const signHour = q(root, "#currency-sign-hour");
    const signFive = q(root, "#currency-sign-five");
    if (!currencySelect || !pricingFields || !signHour || !signFive) return;

    if (currencySelect.dataset.sdBound === "1") return;
    currencySelect.dataset.sdBound = "1";

    function extractSign(optionText) {
      const m = (optionText || "").match(/\(([^)]+)\)\s*$/);
      return m ? m[1] : "";
    }

    function update() {
      const hasCurrency = currencySelect.value && currencySelect.value !== "";
      if (!hasCurrency) {
        pricingFields.style.display = "none";
        return;
      }
      const opt = currencySelect.options[currencySelect.selectedIndex];
      const sign = extractSign(opt ? opt.text : "") || "$";
      signHour.textContent = sign;
      signFive.textContent = sign;
      pricingFields.style.display = "block";
    }

    currencySelect.addEventListener("change", update);
    update();
  }

  /* -------------------------
     6) Profession chip selector (events)
  ------------------------- */
  function initProfessionChipPicker(root) {
    const picker = q(root, ".profession-picker");
    if (!picker) return;

    if (picker.dataset.sdInit === "1") return;
    picker.dataset.sdInit = "1";

    const chips = qa(picker, ".profession-chip");

    function syncChipState(chip) {
      const checkbox = chip.querySelector("input.profession-checkbox");
      if (!checkbox) return;
      chip.classList.toggle("is-selected", checkbox.checked);
    }

    chips.forEach((chip) => {
      const checkbox = chip.querySelector("input.profession-checkbox");
      if (!checkbox) return;

      syncChipState(chip);

      chip.addEventListener("click", (e) => {
        e.preventDefault();
        checkbox.checked = !checkbox.checked;
        syncChipState(chip);
      });
    });

    qa(picker, ".profession-select-all").forEach((btn) => {
      btn.addEventListener("click", () => {
        const groupId = btn.getAttribute("data-group");
        const group = picker.querySelector(`.profession-group[data-group="${groupId}"]`);
        if (!group) return;

        const groupCbs = group.querySelectorAll(".profession-chip input.profession-checkbox");
        const anyUnchecked = Array.from(groupCbs).some((cb) => !cb.checked);
        groupCbs.forEach((cb) => (cb.checked = anyUnchecked));
        group.querySelectorAll(".profession-chip").forEach(syncChipState);
      });
    });
  }

  /* -------------------------
     7) Calendar date range selector (busy time page)
     (unchanged logic, but made safe for repeated init)
  ------------------------- */
  function initBusyCalendarRange(root) {
    const days = qa(root, ".cal-day[data-date]");
    const startInp = q(root, "#cal-start-date");
    const endInp = q(root, "#cal-end-date");
    const label = q(root, "#cal-selected-label");

    const timedWrap = q(root, "#cal-timed-inputs");
    const allDayRadio = q(root, 'input[name="busy_mode"][value="all_day"]');
    const timedRadio = q(root, 'input[name="busy_mode"][value="timed"]');

    const startHour = q(root, 'select[name="start_hour"]');
    const startMin = q(root, 'select[name="start_min"]');
    const endHour = q(root, 'select[name="end_hour"]');
    const endMin = q(root, 'select[name="end_min"]');

    const removeWrap = q(root, "#remove-busy-wrap");
    const removeDayInput = q(root, "#remove-busy-day");

    if (!days.length || !startInp || !endInp || !label) return;

    // prevent double init
    const marker = q(root, "#calendarBusyRangeInitMarker");
    if (marker) return;
    // create a hidden marker so we don't bind twice
    const m = document.createElement("div");
    m.id = "calendarBusyRangeInitMarker";
    m.style.display = "none";
    (q(root, ".calendar-wrap") || document.body).appendChild(m);

    let start = null;
    let end = null;

    function fmt(d) {
      const [y, mo, dd] = d.split("-").map(Number);
      const dt = new Date(y, mo - 1, dd);
      return dt.toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    }

    function clearActive() {
      days.forEach((btn) => btn.classList.remove("is-selected", "is-in-range"));
    }

    function applyActive() {
      clearActive();
      if (!start) return;

      const s = new Date(start);
      const e = new Date(end || start);

      days.forEach((btn) => {
        const d = btn.getAttribute("data-date");
        const dt = new Date(d);
        if (+dt === +s || +dt === +e) btn.classList.add("is-selected");
        if (dt >= s && dt <= e) btn.classList.add("is-in-range");
      });
    }

    function setTimedVisible(isTimed) {
      if (!timedWrap) return;
      timedWrap.style.display = isTimed ? "flex" : "none";
    }

    function setTimeInputs(startStr, endStr) {
      const [sh, sm] = (startStr || "00:00").split(":");
      const [eh, em] = (endStr || "00:00").split(":");
      if (startHour) startHour.value = sh;
      if (startMin) startMin.value = sm;
      if (endHour) endHour.value = eh;
      if (endMin) endMin.value = em;
    }

    function syncHiddenDates() {
      startInp.value = start || "";
      endInp.value = end || start || "";
    }

    function syncLabelDefault() {
      if (!start) {
        label.textContent = "None";
        return;
      }
      if (!end || end === start) label.textContent = fmt(start);
      else label.textContent = `${fmt(start)} – ${fmt(end)}`;
    }

    function parseBusy(btn) {
      const raw = btn.getAttribute("data-busy");
      if (!raw) return [];
      try {
        const items = JSON.parse(raw);
        return Array.isArray(items) ? items : [];
      } catch (e) {
        return [];
      }
    }

    function showRemoveBusy(dayStr) {
      if (!removeWrap || !removeDayInput) return;
      removeWrap.style.display = "block";
      removeDayInput.value = dayStr;
    }

    function hideRemoveBusy() {
      if (!removeWrap || !removeDayInput) return;
      removeWrap.style.display = "none";
      removeDayInput.value = "";
    }

    function showBusyInfoIfSingleDay(btn) {
      if (end && end !== start) return false;

      const items = parseBusy(btn);
      if (!items.length) return false;

      const dateStr = btn.getAttribute("data-date");
      const base = fmt(dateStr);
      const first = items[0];

      showRemoveBusy(dateStr);

      if (first.all_day) {
        label.textContent = `${base} — Busy all day`;
        if (allDayRadio) allDayRadio.checked = true;
        setTimedVisible(false);
      } else {
        label.textContent = `${base} — Busy ${first.start}–${first.end}`;
        if (timedRadio) timedRadio.checked = true;
        setTimedVisible(true);
        setTimeInputs(first.start, first.end);
      }

      if (items.length > 1) label.textContent += ` (+${items.length - 1} more)`;
      return true;
    }

    days.forEach((btn) => {
      btn.addEventListener("click", () => {
        const d = btn.getAttribute("data-date");

        if (!start || (start && end)) {
          start = d;
          end = null;
        } else {
          end = d;
          if (new Date(end) < new Date(start)) {
            const tmp = start;
            start = end;
            end = tmp;
          }
        }

        applyActive();
        syncHiddenDates();

        if (end && end !== start) {
          hideRemoveBusy();
          syncLabelDefault();
          return;
        }

        if (!showBusyInfoIfSingleDay(btn)) {
          hideRemoveBusy();
          syncLabelDefault();
        }
      });
    });

    const todayBtn = q(root, ".cal-day.is-today[data-date]");
    if (todayBtn) {
      start = todayBtn.getAttribute("data-date");
      end = null;
      applyActive();
      syncHiddenDates();

      if (!showBusyInfoIfSingleDay(todayBtn)) {
        hideRemoveBusy();
        syncLabelDefault();
      }
    } else {
      hideRemoveBusy();
      syncHiddenDates();
      syncLabelDefault();
    }
  }

  /* -------------------------
     8) Toggle timed inputs UI (busy time page)
  ------------------------- */
  function initBusyModeToggle(root) {
    const radios = qa(root, 'input[name="busy_mode"]');
    const timed = q(root, "#cal-timed-inputs");
    if (!radios.length || !timed) return;

    if (timed.dataset.sdBound === "1") return;
    timed.dataset.sdBound = "1";

    function update() {
      const checked = document.querySelector('input[name="busy_mode"]:checked');
      timed.style.display = checked && checked.value === "timed" ? "flex" : "none";
    }

    radios.forEach((r) => r.addEventListener("change", update));
    update();
  }

  /* -------------------------
     9) Public calendar day modal (read-only + time range offer)
     NOTE: pro_id is in PUBLIC_CAL_BOOKING_URL path already.
  ------------------------- */
  function initPublicCalendarModal(root) {
    const dayEls = qa(root, ".cal-day-click[data-date]");
    if (!dayEls.length) return;

    const modalEl = document.getElementById("calDayModal");
    if (!modalEl || typeof bootstrap === "undefined") return;

    // prevent double-binding
    if (modalEl.dataset.sdBound === "1") return;
    modalEl.dataset.sdBound = "1";

    const modal = new bootstrap.Modal(modalEl);

    const titleEl = document.getElementById("calDayModalTitle");
    const subEl = document.getElementById("calDayModalSub");

    const bookedWrap = document.getElementById("calModalBookedWrap");
    const busyWrap = document.getElementById("calModalBusyWrap");
    const bookedList = document.getElementById("calModalBookedList");
    const busyList = document.getElementById("calModalBusyList");
    const emptyEl = document.getElementById("calModalEmpty");

    const ctaWrap = document.getElementById("calModalCTA");
    const makeOfferBtn = document.getElementById("calModalMakeOfferBtn");
    const errEl = document.getElementById("calOfferErr");

    const shSel = document.getElementById("calOfferStartHour");
    const smSel = document.getElementById("calOfferStartMin");
    const ehSel = document.getElementById("calOfferEndHour");
    const emSel = document.getElementById("calOfferEndMin");

    function safeJsonParse(raw) {
      if (!raw) return [];
      try {
        const v = JSON.parse(raw);
        return Array.isArray(v) ? v : [];
      } catch (e) {
        return [];
      }
    }

    function fillHours(selectEl) {
      if (!selectEl) return;
      if (selectEl.options && selectEl.options.length) return;
      selectEl.innerHTML = "";
      for (let h = 0; h <= 23; h++) {
        const opt = document.createElement("option");
        opt.value = pad2(h);
        opt.textContent = pad2(h);
        selectEl.appendChild(opt);
      }
    }

    function isPastDate(dateStr) {
      if (!dateStr) return false;
      const [y, m, d] = dateStr.split("-").map(Number);
      if (!y || !m || !d) return false;

      const chosen = new Date(y, m - 1, d);
      chosen.setHours(0, 0, 0, 0);

      const today = new Date();
      today.setHours(0, 0, 0, 0);

      return chosen < today;
    }

    function showError(msg) {
      if (!errEl) return;
      errEl.textContent = msg;
      errEl.style.display = "block";
    }

    function clearError() {
      if (!errEl) return;
      errEl.textContent = "";
      errEl.style.display = "none";
    }

    function disableOfferBtn(text) {
      if (!makeOfferBtn) return;
      makeOfferBtn.href = "#";
      makeOfferBtn.classList.add("disabled");
      makeOfferBtn.setAttribute("aria-disabled", "true");
      makeOfferBtn.setAttribute("tabindex", "-1");
      makeOfferBtn.textContent = text || "Unavailable";
    }

    function enableOfferBtn(href) {
      if (!makeOfferBtn) return;
      makeOfferBtn.classList.remove("disabled");
      makeOfferBtn.removeAttribute("aria-disabled");
      makeOfferBtn.removeAttribute("tabindex");
      makeOfferBtn.textContent = "Make offer";
      makeOfferBtn.href = href;
    }

    function clear() {
      if (bookedList) bookedList.innerHTML = "";
      if (busyList) busyList.innerHTML = "";
      if (bookedWrap) bookedWrap.style.display = "none";
      if (busyWrap) busyWrap.style.display = "none";
      if (emptyEl) emptyEl.style.display = "none";
      if (subEl) subEl.textContent = "";

      if (ctaWrap) ctaWrap.style.display = "none";
      clearError();
      if (makeOfferBtn) makeOfferBtn.href = "#";
    }

    function addBookedItem(item) {
      const card = document.createElement("div");
      card.className = "cal-modal-card";

      const name = document.createElement("div");
      name.className = "cal-modal-title";
      name.textContent = item.name || "Event";

      const meta = document.createElement("div");
      meta.className = "cal-modal-sub";
      meta.textContent = item.label ? item.label : "Time not specified";

      card.appendChild(name);
      card.appendChild(meta);

      if (item.is_locked && (item.accepted_name || item.accepted_avatar)) {
        const row = document.createElement("div");
        row.className = "cal-accepted-pro";

        if (item.accepted_avatar) {
          const img = document.createElement("img");
          img.src = item.accepted_avatar;
          img.alt = item.accepted_name || "Accepted professional";
          img.className = "cal-accepted-avatar";
          row.appendChild(img);
        }

        const info = document.createElement("div");
        info.className = "cal-accepted-meta";
        info.innerHTML = `
          <div class="cal-accepted-title">Accepted professional</div>
          <div class="cal-accepted-name">${item.accepted_name || ""}</div>
        `;
        row.appendChild(info);

        card.appendChild(row);
      }

      const pillRow = document.createElement("div");
      pillRow.className = "d-flex flex-wrap gap-2 mt-2";

      const pill = document.createElement("span");
      pill.className = "cal-pill";
      pill.innerHTML = item.is_locked ? `<strong>Locked</strong>` : `<strong>Booked</strong>`;

      pillRow.appendChild(pill);
      card.appendChild(pillRow);

      bookedList.appendChild(card);
    }

    function addBusyItem(item) {
      const card = document.createElement("div");
      card.className = "cal-modal-card";

      const name = document.createElement("div");
      name.className = "cal-modal-title";
      name.textContent = "Unavailable";

      const meta = document.createElement("div");
      meta.className = "cal-modal-sub";
      meta.textContent = item.all_day
        ? "Busy all day"
        : `Busy ${item.start || "00:00"}–${item.end || "00:00"}`;

      const pillRow = document.createElement("div");
      pillRow.className = "d-flex flex-wrap gap-2 mt-2";

      const pill = document.createElement("span");
      pill.className = "cal-pill";
      pill.innerHTML = item.all_day
        ? `<strong>All day</strong>`
        : `<strong>${item.start || "--:--"}–${item.end || "--:--"}</strong>`;

      pillRow.appendChild(pill);

      card.appendChild(name);
      card.appendChild(meta);
      card.appendChild(pillRow);

      if (item.note) {
        const note = document.createElement("div");
        note.className = "mt-2 text-white-50";
        note.style.whiteSpace = "pre-line";
        note.textContent = item.note;
        card.appendChild(note);
      }

      busyList.appendChild(card);
    }

    function updateOfferLink(activeDate, isPastFlag) {
      const base = window.PUBLIC_CAL_BOOKING_URL;
      if (!ctaWrap || !makeOfferBtn || !base) return;

      ctaWrap.style.display = "block";

      const past = (isPastFlag === "1") || isPastDate(activeDate);
      if (past) {
        clearError();
        disableOfferBtn("Unavailable (past date)");
        return;
      }

      const sh = shSel ? shSel.value : "00";
      const sm = smSel ? smSel.value : "00";
      const eh = ehSel ? ehSel.value : "00";
      const em = emSel ? emSel.value : "00";

      const start = `${sh}:${sm}`;
      const end = `${eh}:${em}`;

      const startMin = (Number(sh) * 60) + Number(sm);
      const endMin = (Number(eh) * 60) + Number(em);

      if (!activeDate) {
        showError("Missing date.");
        disableOfferBtn("Unavailable");
        return;
      }

      if (endMin <= startMin) {
        showError("End time must be after start time.");
        disableOfferBtn("Fix time range");
        return;
      }

      clearError();

      const href =
        `${base}` +
        `?date=${encodeURIComponent(activeDate)}` +
        `&start=${encodeURIComponent(start)}` +
        `&end=${encodeURIComponent(end)}`;

      enableOfferBtn(href);
    }

    function openFor(el) {
      clear();

      const dateStr = el.getAttribute("data-date") || "";
      const isPastFlag = el.getAttribute("data-is-past") || "0";

      const label = el.getAttribute("data-date-label") || dateStr || "Day details";
      if (titleEl) titleEl.textContent = label;

      const booked = safeJsonParse(el.getAttribute("data-booked"));
      const busy = safeJsonParse(el.getAttribute("data-busy"));

      if (booked.length && bookedWrap) {
        bookedWrap.style.display = "block";
        booked.forEach(addBookedItem);
      }

      if (busy.length && busyWrap) {
        busyWrap.style.display = "block";
        busy.forEach(addBusyItem);
      }

      if (!booked.length && !busy.length) {
        if (emptyEl) emptyEl.style.display = "block";

        modalEl.setAttribute("data-active-date", dateStr);
        modalEl.setAttribute("data-active-is-past", isPastFlag);

        fillHours(shSel);
        fillHours(ehSel);

        // defaults UI only
        if (shSel && !shSel.value) shSel.value = "10";
        if (smSel && !smSel.value) smSel.value = "00";
        if (ehSel && !ehSel.value) ehSel.value = "12";
        if (emSel && !emSel.value) emSel.value = "00";

        updateOfferLink(dateStr, isPastFlag);
      }

      modal.show();
    }

    function onTimeChange() {
      const d = modalEl.getAttribute("data-active-date") || "";
      const past = modalEl.getAttribute("data-active-is-past") || "0";
      if (d) updateOfferLink(d, past);
    }

    [shSel, smSel, ehSel, emSel].forEach((sel) => {
      if (!sel) return;
      sel.addEventListener("change", onTimeChange);
    });

    dayEls.forEach((el) => {
      el.addEventListener("click", () => openFor(el));
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openFor(el);
        }
      });
    });
  }

  /* -------------------------
     10) Dashboard sidebar collapse
  ------------------------- */
  function initDashboardSidebar(root) {
    const layout = document.getElementById("dashLayout");
    const btn = document.getElementById("dashToggle");
    if (!layout || !btn) return;

    if (btn.dataset.sdBound === "1") return;
    btn.dataset.sdBound = "1";

    const key = "dash_sidebar_collapsed";

    function setCollapsed(v) {
      layout.classList.toggle("is-collapsed", v);
      try {
        localStorage.setItem(key, v ? "1" : "0");
      } catch (e) {}
    }

    try {
      setCollapsed(localStorage.getItem(key) === "1");
    } catch (e) {}

    btn.addEventListener("click", () => {
      setCollapsed(!layout.classList.contains("is-collapsed"));
    });
  }

  /* -------------------------
     Main initializer
  ------------------------- */
  Showdan.init = function (root) {
    const r = root || document;

    initAccountTypeToggle(r);
    initDobWheel(r);
    initExperienceWheel(r);
    initAboutWordCounter(r);
    initCurrencyPricing(r);
    initProfessionChipPicker(r);

    initBusyCalendarRange(r);
    initBusyModeToggle(r);

    initPublicCalendarModal(r);

    initDashboardSidebar(r);
  };

  /* -------------------------
     Boot on full page load
  ------------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    Showdan.init(document);
  });

  /* -------------------------
     Boot on HTMX swaps (dashboard dynamic pages)
     - htmx:load fires on new content load
     - htmx:afterSwap fires after swap into target
  ------------------------- */
  document.addEventListener("htmx:load", (evt) => {
    // evt.detail.elt is the element that was loaded/swapped
    const root = (evt && evt.detail && evt.detail.elt) ? evt.detail.elt : document;
    Showdan.init(root);
  });

  document.addEventListener("htmx:afterSwap", (evt) => {
    const root = (evt && evt.target) ? evt.target : document;
    Showdan.init(root);
  });
})();

function initAutoDismissAlerts(root = document) {
  const alerts = root.querySelectorAll(".alert.js-auto-dismiss:not([data-auto-dismiss-bound])");
  if (!alerts.length) return;

  alerts.forEach((el) => {
    el.setAttribute("data-auto-dismiss-bound", "1");

    window.setTimeout(() => {
      // Prefer Bootstrap’s Alert API if available
      if (window.bootstrap?.Alert) {
        window.bootstrap.Alert.getOrCreateInstance(el).close();
      } else {
        // Fallback
        el.classList.remove("show");
        window.setTimeout(() => el.remove(), 200);
      }
    }, 3000);
  });
}

// Run on initial load
document.addEventListener("DOMContentLoaded", () => initAutoDismissAlerts());

// Run after HTMX content swaps (this is the missing piece for many setups)
document.addEventListener("htmx:afterSwap", (e) => {
  initAutoDismissAlerts(e.target);
});


  (function () {
    // sync range + inputs
    const minRange = document.getElementById("minRange");
    const maxRange = document.getElementById("maxRange");
    const minPrice = document.getElementById("minPrice");
    const maxPrice = document.getElementById("maxPrice");
    if (!minRange || !maxRange || !minPrice || !maxPrice) return;

    function clamp() {
      let minV = Number(minRange.value);
      let maxV = Number(maxRange.value);
      if (minV > maxV) [minV, maxV] = [maxV, minV];

      minRange.value = minV;
      maxRange.value = maxV;
      minPrice.value = minV;
      maxPrice.value = maxV;
    }

    minRange.addEventListener("input", clamp);
    maxRange.addEventListener("input", clamp);

    minPrice.addEventListener("input", () => {
      const v = Number(minPrice.value || minRange.min);
      minRange.value = v;
      clamp();
    });

    maxPrice.addEventListener("input", () => {
      const v = Number(maxPrice.value || maxRange.max);
      maxRange.value = v;
      clamp();
    });

    // chip active styling
    document.querySelectorAll(".filter-chip input").forEach((inp) => {
      inp.addEventListener("change", () => {
        const label = inp.closest(".filter-chip");
        if (!label) return;

        if (inp.type === "radio") {
          // clear all radios in this group UI
          const group = inp.name;
          document.querySelectorAll(`input[name="${group}"]`).forEach((r) => {
            const lab = r.closest(".filter-chip");
            if (lab) lab.classList.toggle("is-active", r.checked);
          });
        } else {
          label.classList.toggle("is-active", inp.checked);
        }
      });
    });

    clamp();
  })();


 // Events filter modal: sync budget sliders <-> inputs
(function () {
  const minI = document.getElementById("minBudget");
  const maxI = document.getElementById("maxBudget");
  const minR = document.getElementById("minBudgetRange");
  const maxR = document.getElementById("maxBudgetRange");
  if (!minI || !maxI || !minR || !maxR) return;

  function clamp() {
    let minV = Number(minI.value || minR.value || 0);
    let maxV = Number(maxI.value || maxR.value || 0);

    if (!Number.isFinite(minV)) minV = Number(minR.min || 0);
    if (!Number.isFinite(maxV)) maxV = Number(maxR.max || 0);

    if (maxV < minV) maxV = minV;

    minI.value = minV;
    maxI.value = maxV;
    minR.value = minV;
    maxR.value = maxV;
  }

  minR.addEventListener("input", () => { minI.value = minR.value; clamp(); });
  maxR.addEventListener("input", () => { maxI.value = maxR.value; clamp(); });

  minI.addEventListener("input", () => { minR.value = minI.value || minR.min; clamp(); });
  maxI.addEventListener("input", () => { maxR.value = maxI.value || maxR.max; clamp(); });

  clamp();
})();

//document.addEventListener("DOMContentLoaded", () => {
//
//  // Account type → toggle professions
//  (function () {
//    const accountType = document.getElementById("id_account_type");
//    const professionsWrapper = document.getElementById("professions-wrapper");
//    if (!accountType || !professionsWrapper) return;
//
//    function toggleProfessions() {
//      professionsWrapper.style.display =
//        accountType.value === "professional" ? "block" : "none";
//    }
//
//    toggleProfessions();
//    accountType.addEventListener("change", toggleProfessions);
//  })();
//
//
//  // DOB wheel picker
//  (function () {
//    const hiddenDob = document.getElementById("id_date_of_birth");
//    const daySel = document.getElementById("dob-day");
//    const monthSel = document.getElementById("dob-month");
//    const yearSel = document.getElementById("dob-year");
//    const output = document.getElementById("dob-output");
//    if (!hiddenDob || !daySel || !monthSel || !yearSel || !output) return;
//
//    const pad2 = (n) => String(n).padStart(2, "0");
//
//    function fillSelect(select, start, end) {
//      select.innerHTML = "";
//      for (let i = start; i <= end; i++) {
//        const opt = document.createElement("option");
//        opt.value = i;
//        opt.textContent = pad2(i);
//        select.appendChild(opt);
//      }
//    }
//
//    fillSelect(daySel, 1, 31);
//    fillSelect(monthSel, 1, 12);
//
//    const thisYear = new Date().getFullYear();
//    const minYear = thisYear - 100;
//    const maxYear = thisYear;
//    yearSel.innerHTML = "";
//    for (let y = maxYear; y >= minYear; y--) {
//      const opt = document.createElement("option");
//      opt.value = y;
//      opt.textContent = y;
//      yearSel.appendChild(opt);
//    }
//
//    function daysInMonth(year, month) {
//      return new Date(year, month, 0).getDate();
//    }
//
//    function setSelected(select, value) {
//      const opts = Array.from(select.options);
//      const idx = opts.findIndex(o => String(o.value) === String(value));
//      if (idx >= 0) select.selectedIndex = idx;
//    }
//
//    function markActive(select) {
//      Array.from(select.options).forEach(opt => opt.classList.remove("dob-active"));
//      const opt = select.options[select.selectedIndex];
//      if (opt) opt.classList.add("dob-active");
//    }
//
//    function clampDayToMonth() {
//      const y = Number(yearSel.value);
//      const m = Number(monthSel.value);
//      const maxD = daysInMonth(y, m);
//
//      const currentD = Number(daySel.value || 1);
//      daySel.innerHTML = "";
//      for (let d = 1; d <= maxD; d++) {
//        const opt = document.createElement("option");
//        opt.value = d;
//        opt.textContent = pad2(d);
//        daySel.appendChild(opt);
//      }
//      setSelected(daySel, Math.min(currentD, maxD));
//    }
//
//    function syncHidden() {
//      const y = Number(yearSel.value);
//      const m = Number(monthSel.value);
//      const d = Number(daySel.value);
//
//      hiddenDob.value = `${y}-${pad2(m)}-${pad2(d)}`;
//      output.textContent = `${pad2(d)}.${pad2(m)}.${y}`;
//
//      markActive(daySel);
//      markActive(monthSel);
//      markActive(yearSel);
//
//      [daySel, monthSel, yearSel].forEach(sel => {
//        const opt = sel.options[sel.selectedIndex];
//        if (opt) opt.scrollIntoView({ block: "center" });
//      });
//    }
//
//    const initial = hiddenDob.value;
//    if (initial && initial.includes("-")) {
//      const [yy, mm, dd] = initial.split("-").map(Number);
//      setSelected(yearSel, yy);
//      setSelected(monthSel, mm);
//      clampDayToMonth();
//      setSelected(daySel, dd);
//    } else {
//      setSelected(monthSel, 7);
//      setSelected(yearSel, thisYear - 20);
//      clampDayToMonth();
//      setSelected(daySel, 7);
//    }
//
//    clampDayToMonth();
//    syncHidden();
//
//    yearSel.addEventListener("change", () => { clampDayToMonth(); syncHidden(); });
//    monthSel.addEventListener("change", () => { clampDayToMonth(); syncHidden(); });
//    daySel.addEventListener("change", syncHidden);
//  })();
//
//
//  // Years of experience wheel
//  (function () {
//    const hiddenExp = document.getElementById("id_years_of_experience");
//    const expSel = document.getElementById("exp-years");
//    const expOut = document.getElementById("exp-output");
//    if (!hiddenExp || !expSel || !expOut) return;
//
//    const maxYears = 60;
//
//    expSel.innerHTML = "";
//    for (let y = 0; y <= maxYears; y++) {
//      const opt = document.createElement("option");
//      opt.value = y;
//      opt.textContent = String(y).padStart(2, "0");
//      expSel.appendChild(opt);
//    }
//
//    function setSelected(select, value) {
//      const opts = Array.from(select.options);
//      const idx = opts.findIndex(o => String(o.value) === String(value));
//      if (idx >= 0) select.selectedIndex = idx;
//    }
//
//    function markActive(select) {
//      Array.from(select.options).forEach(opt => opt.classList.remove("exp-active"));
//      const opt = select.options[select.selectedIndex];
//      if (opt) opt.classList.add("exp-active");
//    }
//
//    function sync() {
//      const val = Number(expSel.value);
//      hiddenExp.value = val;
//      expOut.textContent = (val === 1) ? "1 year" : `${val} years`;
//      markActive(expSel);
//
//      const opt = expSel.options[expSel.selectedIndex];
//      if (opt) opt.scrollIntoView({ block: "center" });
//    }
//
//    const initial = hiddenExp.value !== "" ? Number(hiddenExp.value) : 0;
//    setSelected(expSel, Number.isFinite(initial) ? initial : 0);
//    sync();
//
//    expSel.addEventListener("change", sync);
//  })();
//
//
//  // About me word counter
//  (function () {
//    const textarea = document.getElementById("id_about_me");
//    const counter = document.getElementById("about-word-count");
//    const MAX = 1000;
//    if (!textarea || !counter) return;
//
//    function countWords(text) {
//      const words = text.trim().match(/\S+/g);
//      return words ? words.length : 0;
//    }
//
//    function update() {
//      const n = countWords(textarea.value);
//      counter.textContent = n;
//      if (n > MAX) {
//        counter.classList.add("text-danger", "fw-semibold");
//      } else {
//        counter.classList.remove("text-danger", "fw-semibold");
//      }
//    }
//
//    textarea.addEventListener("input", update);
//    update();
//  })();
//
//
//  // Currency sign + show/hide pricing fields
//  (function () {
//    const currencySelect = document.getElementById("id_currency");
//    const pricingFields = document.getElementById("pricing-fields");
//    const signHour = document.getElementById("currency-sign-hour");
//    const signFive = document.getElementById("currency-sign-five");
//    if (!currencySelect || !pricingFields || !signHour || !signFive) return;
//
//    function extractSign(optionText) {
//      const m = optionText.match(/\(([^)]+)\)\s*$/);
//      return m ? m[1] : "";
//    }
//
//    function update() {
//      const hasCurrency = currencySelect.value && currencySelect.value !== "";
//      if (!hasCurrency) {
//        pricingFields.style.display = "none";
//        return;
//      }
//      const opt = currencySelect.options[currencySelect.selectedIndex];
//      const sign = extractSign(opt.text) || "$";
//      signHour.textContent = sign;
//      signFive.textContent = sign;
//      pricingFields.style.display = "block";
//    }
//
//    currencySelect.addEventListener("change", update);
//    update();
//  })();
//  /* ===============================
//     Profession chip selector (events)
//  =============================== */
//  const picker = document.querySelector(".profession-picker");
//  if (picker) {
//    const chips = picker.querySelectorAll(".profession-chip");
//
//    function syncChipState(chip) {
//      const checkbox = chip.querySelector("input.profession-checkbox");
//      if (!checkbox) return;
//      chip.classList.toggle("is-selected", checkbox.checked);
//    }
//
//    chips.forEach((chip) => {
//      const checkbox = chip.querySelector("input.profession-checkbox");
//      if (!checkbox) return;
//
//      // initial state
//      syncChipState(chip);
//
//      chip.addEventListener("click", (e) => {
//        e.preventDefault();
//        checkbox.checked = !checkbox.checked;
//        syncChipState(chip);
//      });
//    });
//
//    // Select all in group
//    picker.querySelectorAll(".profession-select-all").forEach((btn) => {
//      btn.addEventListener("click", () => {
//        const groupId = btn.getAttribute("data-group");
//        const group = picker.querySelector(
//          `.profession-group[data-group="${groupId}"]`
//        );
//        if (!group) return;
//
//        const groupChips = group.querySelectorAll(
//          ".profession-chip input.profession-checkbox"
//        );
//
//        // If any unchecked → select all, else unselect all
//        const anyUnchecked = Array.from(groupChips).some(cb => !cb.checked);
//
//        groupChips.forEach(cb => { cb.checked = anyUnchecked; });
//        group.querySelectorAll(".profession-chip").forEach(syncChipState);
//      });
//    });
//  }
//});
//
//
///* ===============================
//   Calendar date range selector
//   + show busy info when clicking a busy day
//   + auto-toggle busy mode (all day / timed)
//   + auto-fill time dropdowns for timed busy blocks
//   + show "Remove busy time" button for busy days
//================================ */
//
//(function () {
//  const days = document.querySelectorAll(".cal-day[data-date]");
//  const startInp = document.getElementById("cal-start-date");
//  const endInp = document.getElementById("cal-end-date");
//  const label = document.getElementById("cal-selected-label");
//
//  // Busy mode + time inputs
//  const timedWrap = document.getElementById("cal-timed-inputs");
//  const allDayRadio = document.querySelector('input[name="busy_mode"][value="all_day"]');
//  const timedRadio = document.querySelector('input[name="busy_mode"][value="timed"]');
//
//  const startHour = document.querySelector('select[name="start_hour"]');
//  const startMin = document.querySelector('select[name="start_min"]');
//  const endHour = document.querySelector('select[name="end_hour"]');
//  const endMin = document.querySelector('select[name="end_min"]');
//
//  // ✅ Remove busy time UI (must exist in calendar.html)
//  // <div id="remove-busy-wrap" style="display:none;"> ... </div>
//  // <input type="hidden" id="remove-busy-day" name="day">
//  const removeWrap = document.getElementById("remove-busy-wrap");
//  const removeDayInput = document.getElementById("remove-busy-day");
//
//  if (!days.length || !startInp || !endInp || !label) return;
//
//  let start = null;
//  let end = null;
//
//  function fmt(d) {
//    // YYYY-MM-DD -> "DD Mon YYYY"
//    const [y, m, dd] = d.split("-").map(Number);
//    const dt = new Date(y, m - 1, dd);
//    return dt.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
//  }
//
//  function clearActive() {
//    days.forEach(btn => btn.classList.remove("is-selected", "is-in-range"));
//  }
//
//  function applyActive() {
//    clearActive();
//    if (!start) return;
//
//    const s = new Date(start);
//    const e = new Date(end || start);
//
//    days.forEach(btn => {
//      const d = btn.getAttribute("data-date");
//      const dt = new Date(d);
//      if (+dt === +s || +dt === +e) btn.classList.add("is-selected");
//      if (dt >= s && dt <= e) btn.classList.add("is-in-range");
//    });
//  }
//
//  function setTimedVisible(isTimed) {
//    if (!timedWrap) return;
//    timedWrap.style.display = isTimed ? "flex" : "none";
//  }
//
//  function setTimeInputs(startStr, endStr) {
//    // startStr/endStr expected "HH:MM"
//    const [sh, sm] = (startStr || "00:00").split(":");
//    const [eh, em] = (endStr || "00:00").split(":");
//
//    if (startHour) startHour.value = sh;
//    if (startMin) startMin.value = sm;
//    if (endHour) endHour.value = eh;
//    if (endMin) endMin.value = em;
//  }
//
//  function syncHiddenDates() {
//    startInp.value = start || "";
//    endInp.value = end || start || "";
//  }
//
//  function syncLabelDefault() {
//    if (!start) {
//      label.textContent = "None";
//      return;
//    }
//    if (!end || end === start) label.textContent = fmt(start);
//    else label.textContent = `${fmt(start)} – ${fmt(end)}`;
//  }
//
//  function parseBusy(btn) {
//    const raw = btn.getAttribute("data-busy");
//    if (!raw) return [];
//    try {
//      const items = JSON.parse(raw);
//      return Array.isArray(items) ? items : [];
//    } catch (e) {
//      return [];
//    }
//  }
//
//  // ✅ Remove busy helpers
//  function showRemoveBusy(dayStr) {
//    if (!removeWrap || !removeDayInput) return;
//    removeWrap.style.display = "block";
//    removeDayInput.value = dayStr;
//  }
//
//  function hideRemoveBusy() {
//    if (!removeWrap || !removeDayInput) return;
//    removeWrap.style.display = "none";
//    removeDayInput.value = "";
//  }
//
//  function showBusyInfoIfSingleDay(btn) {
//    // Only show busy info if selection is single-day
//    if (end && end !== start) return false;
//
//    const items = parseBusy(btn);
//    if (!items.length) return false;
//
//    const dateStr = btn.getAttribute("data-date");
//    const base = fmt(dateStr);
//    const first = items[0];
//
//    // ✅ show remove busy button for this day
//    showRemoveBusy(dateStr);
//
//    if (first.all_day) {
//      label.textContent = `${base} — Busy all day`;
//      if (allDayRadio) allDayRadio.checked = true;
//      setTimedVisible(false);
//    } else {
//      label.textContent = `${base} — Busy ${first.start}–${first.end}`;
//      if (timedRadio) timedRadio.checked = true;
//      setTimedVisible(true);
//      setTimeInputs(first.start, first.end);
//    }
//
//    if (items.length > 1) {
//      label.textContent += ` (+${items.length - 1} more)`;
//    }
//
//    return true;
//  }
//
//  days.forEach(btn => {
//    btn.addEventListener("click", () => {
//      const d = btn.getAttribute("data-date");
//
//      // Range selection (click start then end)
//      if (!start || (start && end)) {
//        start = d;
//        end = null;
//      } else {
//        end = d;
//        // normalize order
//        if (new Date(end) < new Date(start)) {
//          const tmp = start; start = end; end = tmp;
//        }
//      }
//
//      applyActive();
//      syncHiddenDates();
//
//      // If range selected, hide remove button (removal is day-specific)
//      if (end && end !== start) {
//        hideRemoveBusy();
//        syncLabelDefault();
//        return;
//      }
//
//      // Single day: show busy info (and remove button) if day is busy
//      if (!showBusyInfoIfSingleDay(btn)) {
//        hideRemoveBusy();
//        syncLabelDefault();
//      }
//    });
//  });
//
//  // default: select today
//  const todayBtn = document.querySelector(".cal-day.is-today[data-date]");
//  if (todayBtn) {
//    start = todayBtn.getAttribute("data-date");
//    end = null;
//    applyActive();
//    syncHiddenDates();
//
//    if (!showBusyInfoIfSingleDay(todayBtn)) {
//      hideRemoveBusy();
//      syncLabelDefault();
//    }
//  } else {
//    hideRemoveBusy();
//    syncHiddenDates();
//    syncLabelDefault();
//  }
//})();
//
//
///* ===============================
//   Toggle timed inputs UI
//================================ */
//(function () {
//  const radios = document.querySelectorAll('input[name="busy_mode"]');
//  const timed = document.getElementById("cal-timed-inputs");
//  if (!radios.length || !timed) return;
//
//  function update() {
//    const checked = document.querySelector('input[name="busy_mode"]:checked');
//    timed.style.display = (checked && checked.value === "timed") ? "flex" : "none";
//  }
//
//  radios.forEach(r => r.addEventListener("change", update));
//  update();
//})();
//
//
//
///* ===============================
//   Public calendar day modal (read-only + make offer with time range)
//   FIX: pro_id is already in PUBLIC_CAL_BOOKING_URL path, so no data-pro needed
//================================ */
//(function () {
//  const dayEls = document.querySelectorAll(".cal-day-click[data-date]");
//  if (!dayEls.length) return;
//
//  const modalEl = document.getElementById("calDayModal");
//  if (!modalEl || typeof bootstrap === "undefined") return;
//
//  const modal = new bootstrap.Modal(modalEl);
//
//  const titleEl = document.getElementById("calDayModalTitle");
//  const subEl = document.getElementById("calDayModalSub");
//
//  const bookedWrap = document.getElementById("calModalBookedWrap");
//  const busyWrap = document.getElementById("calModalBusyWrap");
//  const bookedList = document.getElementById("calModalBookedList");
//  const busyList = document.getElementById("calModalBusyList");
//  const emptyEl = document.getElementById("calModalEmpty");
//
//  const ctaWrap = document.getElementById("calModalCTA");
//  const makeOfferBtn = document.getElementById("calModalMakeOfferBtn");
//  const errEl = document.getElementById("calOfferErr");
//
//  const shSel = document.getElementById("calOfferStartHour");
//  const smSel = document.getElementById("calOfferStartMin");
//  const ehSel = document.getElementById("calOfferEndHour");
//  const emSel = document.getElementById("calOfferEndMin");
//
//  function safeJsonParse(raw) {
//    if (!raw) return [];
//    try {
//      const v = JSON.parse(raw);
//      return Array.isArray(v) ? v : [];
//    } catch (e) {
//      return [];
//    }
//  }
//
//  function pad2(n) { return String(n).padStart(2, "0"); }
//
//  function fillHours(selectEl) {
//    if (!selectEl) return;
//    if (selectEl.options && selectEl.options.length) return; // fill once
//    selectEl.innerHTML = "";
//    for (let h = 0; h <= 23; h++) {
//      const opt = document.createElement("option");
//      opt.value = pad2(h);
//      opt.textContent = pad2(h);
//      selectEl.appendChild(opt);
//    }
//  }
//
//  function isPastDate(dateStr) {
//    if (!dateStr) return false;
//    const [y, m, d] = dateStr.split("-").map(Number);
//    if (!y || !m || !d) return false;
//
//    const chosen = new Date(y, m - 1, d);
//    chosen.setHours(0, 0, 0, 0);
//
//    const today = new Date();
//    today.setHours(0, 0, 0, 0);
//
//    return chosen < today;
//  }
//
//  function showError(msg) {
//    if (!errEl) return;
//    errEl.textContent = msg;
//    errEl.style.display = "block";
//  }
//
//  function clearError() {
//    if (!errEl) return;
//    errEl.textContent = "";
//    errEl.style.display = "none";
//  }
//
//  function disableOfferBtn(text) {
//    if (!makeOfferBtn) return;
//    makeOfferBtn.href = "#";
//    makeOfferBtn.classList.add("disabled");
//    makeOfferBtn.setAttribute("aria-disabled", "true");
//    makeOfferBtn.setAttribute("tabindex", "-1");
//    makeOfferBtn.textContent = text || "Unavailable";
//  }
//
//  function enableOfferBtn(href) {
//    if (!makeOfferBtn) return;
//    makeOfferBtn.classList.remove("disabled");
//    makeOfferBtn.removeAttribute("aria-disabled");
//    makeOfferBtn.removeAttribute("tabindex");
//    makeOfferBtn.textContent = "Make offer";
//    makeOfferBtn.href = href;
//  }
//
//  function clear() {
//    bookedList.innerHTML = "";
//    busyList.innerHTML = "";
//    bookedWrap.style.display = "none";
//    busyWrap.style.display = "none";
//    emptyEl.style.display = "none";
//    subEl.textContent = "";
//
//    if (ctaWrap) ctaWrap.style.display = "none";
//    clearError();
//    if (makeOfferBtn) makeOfferBtn.href = "#";
//  }
//
//  function addBookedItem(item) {
//    const card = document.createElement("div");
//    card.className = "cal-modal-card";
//
//    const name = document.createElement("div");
//    name.className = "cal-modal-title";
//    name.textContent = item.name || "Event";
//
//    const meta = document.createElement("div");
//    meta.className = "cal-modal-sub";
//    meta.textContent = item.label ? item.label : "Time not specified";
//
//    card.appendChild(name);
//    card.appendChild(meta);
//
//    if (item.is_locked && (item.accepted_name || item.accepted_avatar)) {
//      const row = document.createElement("div");
//      row.className = "cal-accepted-pro";
//
//      if (item.accepted_avatar) {
//        const img = document.createElement("img");
//        img.src = item.accepted_avatar;
//        img.alt = item.accepted_name || "Accepted professional";
//        img.className = "cal-accepted-avatar";
//        row.appendChild(img);
//      }
//
//      const info = document.createElement("div");
//      info.className = "cal-accepted-meta";
//      info.innerHTML = `
//        <div class="cal-accepted-title">Accepted professional</div>
//        <div class="cal-accepted-name">${item.accepted_name || ""}</div>
//      `;
//      row.appendChild(info);
//
//      card.appendChild(row);
//    }
//
//    const pillRow = document.createElement("div");
//    pillRow.className = "d-flex flex-wrap gap-2 mt-2";
//
//    const pill = document.createElement("span");
//    pill.className = "cal-pill";
//    pill.innerHTML = item.is_locked ? `<strong>Locked</strong>` : `<strong>Booked</strong>`;
//
//    pillRow.appendChild(pill);
//    card.appendChild(pillRow);
//
//    bookedList.appendChild(card);
//  }
//
//  function addBusyItem(item) {
//    const card = document.createElement("div");
//    card.className = "cal-modal-card";
//
//    const name = document.createElement("div");
//    name.className = "cal-modal-title";
//    name.textContent = "Unavailable";
//
//    const meta = document.createElement("div");
//    meta.className = "cal-modal-sub";
//    meta.textContent = item.all_day
//      ? "Busy all day"
//      : `Busy ${item.start || "00:00"}–${item.end || "00:00"}`;
//
//    const pillRow = document.createElement("div");
//    pillRow.className = "d-flex flex-wrap gap-2 mt-2";
//
//    const pill = document.createElement("span");
//    pill.className = "cal-pill";
//    pill.innerHTML = item.all_day
//      ? `<strong>All day</strong>`
//      : `<strong>${item.start || "--:--"}–${item.end || "--:--"}</strong>`;
//
//    pillRow.appendChild(pill);
//
//    card.appendChild(name);
//    card.appendChild(meta);
//    card.appendChild(pillRow);
//
//    if (item.note) {
//      const note = document.createElement("div");
//      note.className = "mt-2 text-white-50";
//      note.style.whiteSpace = "pre-line";
//      note.textContent = item.note;
//      card.appendChild(note);
//    }
//
//    busyList.appendChild(card);
//  }
//
//  function updateOfferLink(activeDate, isPastFlag) {
//    const base = window.PUBLIC_CAL_BOOKING_URL;
//    if (!ctaWrap || !makeOfferBtn || !base) return;
//
//    ctaWrap.style.display = "block";
//
//    const past = (isPastFlag === "1") || isPastDate(activeDate);
//    if (past) {
//      clearError();
//      disableOfferBtn("Unavailable (past date)");
//      return;
//    }
//
//    const sh = shSel ? shSel.value : "00";
//    const sm = smSel ? smSel.value : "00";
//    const eh = ehSel ? ehSel.value : "00";
//    const em = emSel ? emSel.value : "00";
//
//    const start = `${sh}:${sm}`;
//    const end = `${eh}:${em}`;
//
//    const startMin = (Number(sh) * 60) + Number(sm);
//    const endMin = (Number(eh) * 60) + Number(em);
//
//    if (!activeDate) {
//      showError("Missing date.");
//      disableOfferBtn("Unavailable");
//      return;
//    }
//
//    if (endMin <= startMin) {
//      showError("End time must be after start time.");
//      disableOfferBtn("Fix time range");
//      return;
//    }
//
//    clearError();
//
//    // ✅ pro_id already in base URL path
//    const href =
//      `${base}` +
//      `?date=${encodeURIComponent(activeDate)}` +
//      `&start=${encodeURIComponent(start)}` +
//      `&end=${encodeURIComponent(end)}`;
//
//    enableOfferBtn(href);
//  }
//
//  function openFor(el) {
//    clear();
//
//    const dateStr = el.getAttribute("data-date") || "";
//    const isPastFlag = el.getAttribute("data-is-past") || "0";
//
//    const label = el.getAttribute("data-date-label") || dateStr || "Day details";
//    titleEl.textContent = label;
//
//    const booked = safeJsonParse(el.getAttribute("data-booked"));
//    const busy = safeJsonParse(el.getAttribute("data-busy"));
//
//    if (booked.length) {
//      bookedWrap.style.display = "block";
//      booked.forEach(addBookedItem);
//    }
//
//    if (busy.length) {
//      busyWrap.style.display = "block";
//      busy.forEach(addBusyItem);
//    }
//
//    if (!booked.length && !busy.length) {
//      emptyEl.style.display = "block";
//
//      modalEl.setAttribute("data-active-date", dateStr);
//      modalEl.setAttribute("data-active-is-past", isPastFlag);
//
//      fillHours(shSel);
//      fillHours(ehSel);
//
//      // default UI values only (backend uses chosen values)
//      if (shSel && !shSel.value) shSel.value = "10";
//      if (smSel && !smSel.value) smSel.value = "00";
//      if (ehSel && !ehSel.value) ehSel.value = "12";
//      if (emSel && !emSel.value) emSel.value = "00";
//
//      updateOfferLink(dateStr, isPastFlag);
//    }
//
//    modal.show();
//  }
//
//  function onTimeChange() {
//    const d = modalEl.getAttribute("data-active-date") || "";
//    const past = modalEl.getAttribute("data-active-is-past") || "0";
//    if (d) updateOfferLink(d, past);
//  }
//
//  [shSel, smSel, ehSel, emSel].forEach((sel) => {
//    if (!sel) return;
//    sel.addEventListener("change", onTimeChange);
//  });
//
//  dayEls.forEach((el) => {
//    el.addEventListener("click", () => openFor(el));
//    el.addEventListener("keydown", (e) => {
//      if (e.key === "Enter" || e.key === " ") {
//        e.preventDefault();
//        openFor(el);
//      }
//    });
//  });
//})();
//
//  (function () {
//    const layout = document.getElementById("dashLayout");
//    const btn = document.getElementById("dashToggle");
//    if (!layout || !btn) return;
//
//    const key = "dash_sidebar_collapsed";
//
//    function setCollapsed(v) {
//      layout.classList.toggle("is-collapsed", v);
//      try { localStorage.setItem(key, v ? "1" : "0"); } catch (e) {}
//    }
//
//    // init
//    try {
//      setCollapsed(localStorage.getItem(key) === "1");
//    } catch (e) {}
//
//    btn.addEventListener("click", () => {
//      setCollapsed(!layout.classList.contains("is-collapsed"));
//    });
//  })();
//
//
//
