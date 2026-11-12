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

  function describeCv() {
    if (!cv.files || !cv.files[0]) {
      cvName.textContent = "لم يُختر ملف بعد";
      return;
    }
    const f = cv.files[0];
    const mb = (f.size / (1024 * 1024)).toFixed(1);
    cvName.textContent = f.name + " — " + mb + " ميغابايت";
    if (f.size > 10 * 1024 * 1024) {
      cvName.textContent += " (يتجاوز الحد 10 ميغابايت)";
    }
  }
  cv.addEventListener("change", describeCv);
  describeCv();

  form.addEventListener("submit", function () {
    submitBtn.disabled = true;
    submitBtn.textContent = "جارٍ الإرسال…";
    // Re-enable after a delay if the server returns the form with errors
    setTimeout(function () {
      submitBtn.disabled = false;
      submitBtn.textContent = "إرسال الطلب";
    }, 12000);
  });

  const err = document.getElementById("form-errors");
  if (err) err.scrollIntoView({ behavior: "smooth", block: "start" });
})();
