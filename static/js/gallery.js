document.addEventListener("DOMContentLoaded", function() {
    const galleryContainer = document.getElementById("photo-gallery");

    const jsonPath = galleryContainer.dataset.json;
    const imageBase = galleryContainer.dataset.imageBase;

    fetch(jsonPath)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(imageFilenames => {
            let galleryHTML = "";

            imageFilenames.forEach(filename => {
                const imageUrl = imageBase + filename;

                galleryHTML += `
                    <div class="col-md-4 mb-4">
                        <a href="${imageUrl}" class="img-hover" data-fancybox="gallery">
                            <span class="icon icon-search"></span>
                            <img src="${imageUrl}" alt="Gallery image" class="img-fluid" loading="lazy">
                        </a>
                    </div>
                `;
            });

            galleryContainer.innerHTML = galleryHTML;
        })
        .catch(error => {
            console.error("Could not load gallery:", error);
            galleryContainer.innerHTML = "<p>Sorry, the photo gallery could not be loaded.</p>";
        });
});
