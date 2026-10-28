(() => {
  "use strict";
  const form = document.getElementById("greet-form");
  const name = document.getElementById("name");
  const result = document.getElementById("result");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    result.textContent = "Calling Python…";
    try {
      const response = await window.kourosh.invoke("greet", { name: name.value });
      result.textContent = response.message;
    } catch (error) {
      result.textContent = `${error.code || "error"}: ${error.message || "bridge call failed"}`;
    }
  });
})();
