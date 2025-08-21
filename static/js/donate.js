document.addEventListener('DOMContentLoaded', function () {
  // Read server-injected config (CSP-safe)
  const cfgEl   = document.getElementById('donation-config');
  const RZP_KEY = cfgEl ? cfgEl.dataset.keyId : '';
  const LOGO_URL = cfgEl ? cfgEl.dataset.logo : '';

  // Toggle forms by donation type
  document.querySelectorAll('input[name="donation-type"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const isIndian = radio.value === 'indian';
      document.getElementById('indian-form').style.display = isIndian ? 'flex' : 'none';
      document.getElementById('overseas-form').style.display = isIndian ? 'none' : 'flex';
    });
  });

  // Amount button helpers
  function setupAmountButtons(containerSel, inputSel) {
    document.querySelectorAll(containerSel + ' .donation-amount').forEach(button => {
      button.addEventListener('click', () => {
        document.querySelectorAll(containerSel + ' .donation-amount').forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        const input = document.querySelector(inputSel);
        if (input) input.value = button.dataset.amount;
      });
    });
  }
  setupAmountButtons('#indian-form', '#indian-custom-amount');
  setupAmountButtons('#overseas-form', '#overseas-custom-amount');

  // Smooth scroll (replaces inline onclick)
  const donateNowBtn = document.getElementById('donate-now-btn');
  if (donateNowBtn) {
    donateNowBtn.addEventListener('click', () => {
      const target = donateNowBtn.getAttribute('data-target') || '#donate-section';
      const el = document.querySelector(target);
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    });
  }

  // Failure overlay
  function showFailureOverlay(errorMessage = 'Unknown error') {
    const failureOverlay = document.getElementById('failure-overlay');
    const failureMessage = document.getElementById('failure-message');
    const timerMessage   = document.getElementById('timer-message');
    const redirectBtn    = document.getElementById('failure-redirect-btn');

    if (failureMessage) {
      failureMessage.textContent =
        `We’re sorry, your payment could not be processed. ${errorMessage ? `Reason: ${errorMessage}.` : ''} Please try again.`;
    }

    if (failureOverlay) failureOverlay.style.display = 'flex';

    let timeLeft = 7;
    if (timerMessage) timerMessage.textContent = `You will return to the donation page in ${timeLeft} seconds`;

    const timer = setInterval(() => {
      timeLeft--;
      if (timerMessage) timerMessage.textContent = `You will return to the donation page in ${timeLeft} seconds`;
      if (timeLeft <= 0) {
        clearInterval(timer);
        if (failureOverlay) failureOverlay.style.display = 'none';
        window.location.href = '/donate';
      }
    }, 1000);

    if (redirectBtn) {
      redirectBtn.onclick = () => {
        clearInterval(timer);
        if (failureOverlay) failureOverlay.style.display = 'none';
        window.location.href = '/donate';
      };
    }
  }

  // Razorpay checkout
  function openRazorpayCheckout(orderId, amount, name, email, loadingOverlay) {
    const options = {
      key: RZP_KEY,
      amount: Math.round(amount * 100),
      currency: "INR",
      name: "Sankalap Ek Sewa Foundation",
      description: "Donation",
      image: LOGO_URL,
      order_id: orderId,
      handler: function (response) {
        fetch('/verify-payment', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_order_id: response.razorpay_order_id,
            razorpay_signature: response.razorpay_signature
          })
        })
        .then(res => res.json())
        .then(data => {
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          if (data.status === 'success') {
            window.location.href = data.redirect_url;
          } else {
            showFailureOverlay(data.error || 'Payment verification failed');
          }
        })
        .catch(error => {
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          showFailureOverlay('An error occurred during payment verification: ' + error.message);
        });
      },
      modal: {
        ondismiss: function () {
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          showFailureOverlay('Payment was cancelled.');
        }
      },
      prefill: { name, email },
      theme: { color: "#f7ca44" }
    };

    const rzp = new Razorpay(options);
    rzp.on('payment.failed', function (response) {
      if (loadingOverlay) loadingOverlay.style.display = 'none';
      showFailureOverlay(response?.error?.description || 'Payment failed.');
    });
    rzp.open();
  }

  // Indian donation
  const indianProceed = document.getElementById('indian-proceed-btn');
  if (indianProceed) {
    indianProceed.addEventListener('click', function () {
      const form = document.getElementById('indian-donation-form');
      if (!form) return;
      if (!form.checkValidity()) {
        form.classList.add('was-validated');
        return;
      }

      const donorName  = document.getElementById('indian-donor-name').value;
      const donorEmail = document.getElementById('indian-donor-email').value;
      const amount     = parseFloat(document.getElementById('indian-custom-amount').value) || 0;
      const loadingOverlay = document.getElementById('loading-overlay');
      if (loadingOverlay) loadingOverlay.style.display = 'flex';

      fetch('/process-donation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          'donor-name': donorName,
          'donor-email': donorEmail,
          'custom-amount': amount
        })
      })
      .then(response => response.json())
      .then(data => {
        if (data.order_id) {
          openRazorpayCheckout(data.order_id, amount, donorName, donorEmail, loadingOverlay);
        } else {
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          showFailureOverlay(data.error || 'Failed to create Razorpay order');
        }
      })
      .catch(error => {
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        showFailureOverlay('An error occurred while processing your donation: ' + error.message);
      });
    });
  }

  // PayPal buttons — init with polling to avoid race with async SDK
  function initPayPalButtons() {
    if (typeof paypal !== 'undefined' && paypal.Buttons) {
      paypal.Buttons({
        createOrder: function () {
          const donorName  = document.getElementById('overseas-donor-name').value;
          const donorEmail = document.getElementById('overseas-donor-email').value;
          const amount     = parseFloat(document.getElementById('overseas-custom-amount').value) || 0;

          if (!donorName || !donorEmail || amount <= 0) {
            alert('Please fill in all fields with a valid amount.');
            return;
          }

          return fetch('/create-paypal-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              'donor-name': donorName,
              'donor-email': donorEmail,
              'amount': amount
            })
          })
          .then(res => res.json())
          .then(data => {
            if (data.orderID) return data.orderID;
            throw new Error(data.error || 'Failed to create PayPal order');
          });
        },
        onApprove: function (data) {
          const loadingOverlay = document.getElementById('loading-overlay');
          if (loadingOverlay) loadingOverlay.style.display = 'flex';

          return fetch('/capture-paypal-payment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ orderID: data.orderID })
          })
          .then(res => res.json())
          .then(data => {
            if (loadingOverlay) loadingOverlay.style.display = 'none';
            if (data.status === 'success') {
              window.location.href = data.redirect_url;
            } else {
              showFailureOverlay(data.error || 'Payment verification failed');
            }
          })
          .catch(error => {
            if (loadingOverlay) loadingOverlay.style.display = 'none';
            showFailureOverlay('An error occurred during payment: ' + error.message);
          });
        },
        onCancel: function () {
          const loadingOverlay = document.getElementById('loading-overlay');
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          showFailureOverlay('Payment was cancelled by the donor.');
        },
        onError: function (err) {
          const loadingOverlay = document.getElementById('loading-overlay');
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          showFailureOverlay('An error occurred during payment: ' + err.message);
        }
      }).render('#paypal-button-container');
      return true;
    }
    return false;
  }

  if (!initPayPalButtons()) {
    window.addEventListener('load', initPayPalButtons);
    let tries = 0;
    const iv = setInterval(() => {
      if (initPayPalButtons() || ++tries > 20) clearInterval(iv);
    }, 250);
  }
});
