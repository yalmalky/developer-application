(function () {
  const root = document.getElementById("projects");
  const countInput = document.getElementById("project_count");
  const addBtn = document.getElementById("add-project");
  const removeBtn = document.getElementById("remove-project");
  const posted = document.getElementById("posted-projects");
  const form = document.getElementById("apply-form");
  const cv = document.getElementById("cv");
  const cvName = document.getElementById("cv-name");
  const submitBtn = document.getElementById("submit-btn");

  function saved(i, key) {
    if (!posted) return "";
    const map = { name: "n", link: "l", role: "r", tech: "t", year: "y", live: "v" };
    return posted.getAttribute("data-" + map[key] + i) || "";
  }

  function projectHtml(i) {
    const name = escapeAttr(saved(i, "name"));
    const link = escapeAttr(saved(i, "link"));
    const role = saved(i, "role");
    const tech = escapeAttr(saved(i, "tech"));
    const year = escapeAttr(saved(i, "year"));
    const live = saved(i, "live");
    return `
      <article class="project" data-index="${i}">
        <h3>المشروع ${i}</h3>
        <div class="grid two">
          <label class="field">
            <span>اسم التطبيق / المشروع *</span>
            <input type="text" name="project_${i}_name" required value="${name}">
          </label>
          <label class="field">
            <span>الرابط (المتجر أو الموقع) *</span>
            <input type="url" name="project_${i}_link" required dir="ltr" placeholder="https://" value="${link}">
          </label>
          <fieldset class="field">
            <legend>دورك بالضبط *</legend>
            <div class="pills wrap">
              <label class="pill"><input type="radio" name="project_${i}_role" value="alone" required ${role === "alone" ? "checked" : ""}> بنيته وحدي</label>
              <label class="pill"><input type="radio" name="project_${i}_role" value="team" ${role === "team" ? "checked" : ""}> ضمن فريق</label>
              <label class="pill"><input type="radio" name="project_${i}_role" value="maintenance" ${role === "maintenance" ? "checked" : ""}> صيانة/تحديث فقط</label>
            </div>
          </fieldset>
          <label class="field">
            <span>التقنيات المستخدمة *</span>
            <input type="text" name="project_${i}_tech" required value="${tech}">
          </label>
          <label class="field">
            <span>السنة *</span>
            <input type="number" name="project_${i}_year" required min="2000" max="2027" value="${year}">
          </label>
          <fieldset class="field">
            <legend>لا يزال يعمل؟ *</legend>
            <div class="pills">
              <label class="pill yes"><input type="radio" name="project_${i}_live" value="yes" required ${live === "yes" ? "checked" : ""}> نعم</label>
              <label class="pill no"><input type="radio" name="project_${i}_live" value="no" ${live === "no" ? "checked" : ""}> لا</label>
            </div>
          </fieldset>
        </div>
      </article>`;
  }

  function escapeAttr(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function currentCount() {
    return root.querySelectorAll(".project").length;
  }

  function render(n) {
    n = Math.min(Math.max(n, 1), 5);
    const html = [];
    for (let i = 1; i <= n; i += 1) html.push(projectHtml(i));
    root.innerHTML = html.join("");
    countInput.value = String(n);
    addBtn.disabled = n >= 5;
    removeBtn.disabled = n <= 1;
  }

  const start = posted ? parseInt(posted.getAttribute("data-count") || "1", 10) : 1;
  render(start || 1);

  addBtn.addEventListener("click", function () {
    if (currentCount() < 5) render(currentCount() + 1);
  });
  removeBtn.addEventListener("click", function () {
    if (currentCount() > 1) render(currentCount() - 1);
  });

  const maxMb = parseInt(cv.getAttribute("data-max-mb") || "25", 10);
  const stashName = cv.getAttribute("data-stash-name") || "";
  const stashInput = document.getElementById("cv_stash");
  const status = document.getElementById("submit-status");
  const clientErr = document.getElementById("client-errors");
  const DRAFT_KEY = "devapp-draft-v1";

  function describeCv() {
    if (!cv.files || !cv.files[0]) {
      cvName.textContent = stashName
        ? "مرفق مسبقًا: " + stashName + " (محفوظ، ما تحتاج ترفعه مرة ثانية)"
        : "لم يُختر ملف بعد";
      return;
    }
    const f = cv.files[0];
    const mb = (f.size / (1024 * 1024)).toFixed(1);
    cvName.textContent = f.name + " — " + mb + " ميغابايت";
    if (f.size > maxMb * 1024 * 1024) {
      cvName.textContent += " (يتجاوز الحد " + maxMb + " ميغابايت)";
    }
  }
  cv.addEventListener("change", describeCv);
  describeCv();

  // ---------- autosave draft on this device (never the CV file) ----------
  function storage() {
    try { const k = "__t"; localStorage.setItem(k, "1"); localStorage.removeItem(k); return localStorage; }
    catch (e) { return null; }
  }
  const ls = storage();
  const SKIP = { csrf_token: 1, cv_stash: 1, website: 1, fax_number: 1, cv: 1 };

  function snapshot() {
    const data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || SKIP[el.name] || el.type === "file" || el.type === "submit" || el.type === "button") return;
      if (el.type === "radio") { if (el.checked) data[el.name] = el.value; return; }
      if (el.type === "checkbox") { data[el.name] = el.checked ? el.value : ""; return; }
      data[el.name] = el.value;
    });
    return data;
  }
  let saveTimer = null;
  function saveDraft() {
    if (!ls) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () {
      try { ls.setItem(DRAFT_KEY, JSON.stringify({ t: Date.now(), d: snapshot() })); } catch (e) {}
    }, 300);
  }
  function restoreDraft() {
    if (!ls) return;
    let draft = null;
    try { draft = JSON.parse(ls.getItem(DRAFT_KEY) || "null"); } catch (e) { draft = null; }
    if (!draft || !draft.d) return;
    if (Date.now() - (draft.t || 0) > 30 * 24 * 3600 * 1000) return;
    const d = draft.d;
    const n = parseInt(d.project_count || "1", 10);
    if (n > currentCount()) render(n);
    let restored = 0;
    Object.keys(d).forEach(function (name) {
      if (name === "project_count") return;
      const els = form.querySelectorAll('[name="' + name.replace(/"/g, "") + '"]');
      if (!els.length) return;
      const first = els[0];
      if (first.type === "radio") {
        const any = Array.prototype.some.call(els, function (e) { return e.checked; });
        if (any || !d[name]) return;
        Array.prototype.forEach.call(els, function (e) { if (e.value === d[name]) { e.checked = true; restored++; } });
      } else if (first.type === "checkbox") {
        if (!first.checked && d[name]) { first.checked = true; restored++; }
      } else if (!first.value && d[name]) {
        // Never overwrite what the server sent back; only fill empty fields.
        first.value = d[name];
        restored++;
      }
    });
    if (restored > 0 && status) {
      status.textContent = "استرجعنا إجاباتك المحفوظة على جهازك. تأكد من إرفاق السيرة الذاتية ثم أرسل.";
    }
  }
  restoreDraft();
  form.addEventListener("input", saveDraft);
  form.addEventListener("change", saveDraft);
  addBtn.addEventListener("click", saveDraft);
  removeBtn.addEventListener("click", saveDraft);
  window.addEventListener("pagehide", function () {
    if (!ls) return;
    try { ls.setItem(DRAFT_KEY, JSON.stringify({ t: Date.now(), d: snapshot() })); } catch (e) {}
  });

  // ---------- check before sending, so the page never reloads just to show an error ----------
  function labelFor(el) {
    const fs = el.closest("fieldset");
    if (fs && fs.querySelector("legend")) return fs.querySelector("legend").textContent.replace("*", "").trim();
    const lab = el.closest("label");
    if (lab && lab.querySelector("span")) return lab.querySelector("span").textContent.replace("*", "").trim();
    return el.name;
  }
  function check() {
    const problems = [];
    let firstBad = null;
    const seenRadio = {};
    form.querySelectorAll(".invalid").forEach(function (e) { e.classList.remove("invalid"); });
    function bad(el, msg) {
      problems.push(msg);
      const box = el.closest("fieldset") || el.closest("label") || el;
      box.classList.add("invalid");
      if (!firstBad) firstBad = box;
    }
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || SKIP[el.name] && el.name !== "cv") return;
      if (el.type === "radio") {
        if (seenRadio[el.name]) return;
        seenRadio[el.name] = 1;
        const group = form.querySelectorAll('input[type="radio"][name="' + el.name + '"]');
        const req = Array.prototype.some.call(group, function (g) { return g.required; });
        const ok = Array.prototype.some.call(group, function (g) { return g.checked; });
        if (req && !ok) bad(el, "اختر إجابة: " + labelFor(el));
        return;
      }
      if (el.type === "checkbox") { if (el.required && !el.checked) bad(el, "علّم على الإقرار قبل الإرسال."); return; }
      if (el.type === "file") {
        const f = el.files && el.files[0];
        if (!f && !(stashInput && stashInput.value)) bad(el, "أرفق السيرة الذاتية (PDF أو Word).");
        else if (f && f.size > maxMb * 1024 * 1024) bad(el, "حجم السيرة الذاتية أكبر من " + maxMb + " ميغابايت. ارفع نسخة أصغر.");
        else if (f && !/\.(pdf|docx?)$/i.test(f.name)) bad(el, "صيغة السيرة الذاتية لازم تكون PDF أو DOC أو DOCX.");
        return;
      }
      const v = (el.value || "").trim();
      if (el.required && !v) { bad(el, "عبّ الحقل: " + labelFor(el)); return; }
      const min = parseInt(el.getAttribute("minlength") || "0", 10);
      if (min && v && v.length < min) bad(el, "اكتب إجابة أطول (" + min + " حرف على الأقل): " + labelFor(el));
      if (el.type === "email" && v && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) bad(el, "البريد الإلكتروني غير صحيح.");
      if (el.type === "url" && v && !/^https?:\/\/\S+$/i.test(v)) bad(el, "الرابط لازم يبدأ بـ https:// : " + labelFor(el));
    });
    return { problems: problems, firstBad: firstBad };
  }

  let sending = false;
  form.addEventListener("submit", function (ev) {
    if (sending) { ev.preventDefault(); return; }
    const r = check();
    if (r.problems.length) {
      ev.preventDefault();
      const ul = clientErr.querySelector("ul");
      ul.innerHTML = "";
      r.problems.slice(0, 12).forEach(function (m) { const li = document.createElement("li"); li.textContent = m; ul.appendChild(li); });
      if (r.problems.length > 12) { const li = document.createElement("li"); li.textContent = "و" + (r.problems.length - 12) + " بنود أخرى مظللة بالأحمر."; ul.appendChild(li); }
      clientErr.hidden = false;
      (r.firstBad || clientErr).scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (navigator.onLine === false) {
      ev.preventDefault();
      if (status) status.textContent = "ما فيه اتصال بالإنترنت الآن. إجاباتك محفوظة؛ أرسل لما يرجع الاتصال.";
      return;
    }
    clientErr.hidden = true;
    saveDraft();
    sending = true;
    submitBtn.disabled = true;
    submitBtn.textContent = "جارٍ الإرسال…";
    if (status) status.textContent = "جارٍ رفع طلبك والسيرة الذاتية. قد يستغرق دقيقة، لا تغلق الصفحة.";
  });
  // If the user comes back (back button / bfcache), make the button usable again.
  window.addEventListener("pageshow", function () {
    sending = false;
    submitBtn.disabled = false;
    submitBtn.textContent = "إرسال الطلب";
  });

  const err = document.getElementById("form-errors");
  if (err) err.scrollIntoView({ behavior: "smooth", block: "start" });
})();
