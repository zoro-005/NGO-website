// submit_fundraiser.js

document.addEventListener('DOMContentLoaded', function() {
    const dataEl = document.getElementById('fundraiser-data');
    const submitFundraiserUrl = dataEl.dataset.submitUrl || "";
    const showClientModal = dataEl.dataset.showModal === 'true';

    const modal = document.getElementById('clientKeyModal');
    const fundraiserForm = document.getElementById('fundraiserForm');

    if (modal) {
        // Redirect if modal is closed without authentication
        $('#clientKeyModal').on('hidden.bs.modal', function () {
            if (!modal.dataset.authenticated) {
                window.location.href = submitFundraiserUrl;
            }
        });

        if (showClientModal) {
            // Show modal via Bootstrap
            $('#clientKeyModal').modal('show');

            // Hide fundraiser form
            if (fundraiserForm) {
                fundraiserForm.classList.add('d-none');
            }
        }
    }
});
