function validateForm(event) {
  event.preventDefault(); // Prevent default submission

  var name = document.getElementById("name").value;
  var email = document.getElementById("email").value;
  var subject = document.getElementById("subject").value;
  var message = document.getElementById("message").value;

  // Basic email validation
  var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    // alert("Please enter a valid email address"); // Optional: Replace with modal or inline message for stricter CSP
    return false;
  }

  // If valid, submit the form
  event.target.submit();
}

function showSuccessMessage() {
  // alert("Message sent successfully!"); // Optional: Replace with inline notification div
}

document.addEventListener("DOMContentLoaded", function() {
  var form = document.getElementById("contactForm");
  if (form) {
    form.addEventListener("submit", validateForm, false);
  }

  var flag = document.getElementById("success-flag");
  if (flag && flag.dataset.message === "true") {
    showSuccessMessage();
  }
});
