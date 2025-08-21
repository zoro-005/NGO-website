document.addEventListener("DOMContentLoaded", function() {
    const form = document.getElementById("join-us-form");

    function validateForm() {
        const name = document.getElementById("name").value.trim();
        const email = document.getElementById("email").value.trim();
        const phone = document.getElementById("phone").value.trim();
        const reason = document.getElementById("reason").value.trim();

        if (!name || !email || !phone || !reason) {
            return false;
        }

        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            return false;
        }

        const phoneRegex = /^\d{10}$/;
        if (!phoneRegex.test(phone)) {
            return false;
        }

        return true;
    }

    if (form) {
        form.addEventListener("submit", function(e) {
            if (!validateForm()) {
                e.preventDefault();
                // Instead of alert, let the server flash handle the error
            }
        });
    }

    if (form) {
        form.addEventListener("submit", function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add("was-validated");
        }, false);
    }
});
