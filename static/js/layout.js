// layout.js

document.addEventListener("DOMContentLoaded", function () {
  // Update current year in footer
  const yearSpan = document.querySelector(".current-year");
  if (yearSpan) {
    yearSpan.textContent = new Date().getFullYear();
  }

  // Navbar toggle
  const toggler = document.getElementById("navbar-toggler");
  const navMenu = document.getElementById("ftco-nav");
  if (toggler && navMenu) {
    toggler.addEventListener("click", () => {
      navMenu.classList.toggle("show");
      toggler.setAttribute("aria-expanded", navMenu.classList.contains("show"));
    });
  }

  // Modal trigger (Bootstrap 4.x requires jQuery API)
  const addFundraiserLink = document.getElementById("addFundraiserLink");
  const clientModalEl = document.getElementById("clientModal");
  if (addFundraiserLink && clientModalEl) {
    addFundraiserLink.addEventListener("click", function (e) {
      e.preventDefault(); // prevent jumping if it's an <a>
      $("#clientModal").modal("show"); // jQuery + Bootstrap 4 API
    });
  }
});

  document.addEventListener("DOMContentLoaded", () => {
    const alerts = document.querySelectorAll(".alert");
    alerts.forEach(alert => {
      setTimeout(() => {
        if (alert.classList.contains("show")) {
          alert.classList.remove("show");
          alert.classList.add("fade");
          setTimeout(() => alert.remove(), 500); // remove after fade
        }
      }, 4000); // 4 seconds visible
    });
  });


