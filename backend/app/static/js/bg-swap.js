// LRIP Swap-and-Blur logic.
// Expects a container element with id="lrip-bg" and attributes:
//  - data-cloudinary: the Cloudinary base URL (without transformations)
//  - data-placeholder: a base64 data URL for the tiny placeholder image
// Optionally you can add data-transform="f_auto,q_auto" to customize transformations.

(function () {
  function init() {
    // Find all containers that declare either a cloudinary url or placeholder
    var containers = document.querySelectorAll('[data-cloudinary], [data-placeholder]');
    if (!containers || containers.length === 0) return;

    containers.forEach(function (container, idx) {
      var cloud = container.dataset.cloudinary || '';
      var placeholder = container.dataset.placeholder || '';
      var transform = container.dataset.transform || 'f_auto,q_auto';

      // Build layers
      var main = document.createElement('div');
      main.className = 'bg-main';
      var placeholderLayer = document.createElement('div');
      placeholderLayer.className = 'bg-placeholder';

      if (placeholder) {
        placeholderLayer.style.backgroundImage = "url('" + placeholder + "')";
      }

      container.appendChild(main);
      container.appendChild(placeholderLayer);

      if (!cloud) return; // no cloud url provided for this container

      // append transformation params to Cloudinary URL
      var separator = cloud.indexOf('?') === -1 ? '?' : '&';
      var highResUrl = cloud + separator + 'tr=' + transform;

      var img = new Image();
      img.crossOrigin = 'anonymous';
      img.src = highResUrl;

      img.onload = function () {
        main.style.backgroundImage = "url('" + highResUrl + "')";
        main.classList.add('visible');
        main.style.opacity = '1';
        placeholderLayer.style.opacity = '0';
      };

      img.onerror = function () {
        // fallback: set main to cloud url without transform
        main.style.backgroundImage = "url('" + cloud + "')";
        main.style.opacity = '1';
        placeholderLayer.style.opacity = '0';
      };
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
