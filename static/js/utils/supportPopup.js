function initSupportPopup(username) {
  const popupKey = `coffeePopupShown_${username}`;
  const firstVisitKey = `firstVisit_${username}`;
  const now = Date.now();

  // Check if popup was already shown in last 24 hours
  const lastShown = localStorage.getItem(popupKey);
  if (lastShown && now - parseInt(lastShown) < 24 * 60 * 60 * 1000) {
    return;
  }

  // Get first visit time
  let firstVisit = localStorage.getItem(firstVisitKey);

  // Reset first visit if it's been more than 24 hours
  if (firstVisit && now - parseInt(firstVisit) > 24 * 60 * 60 * 1000) {
    firstVisit = null;
  }

  // Set new first visit time if needed
  if (!firstVisit) {
    firstVisit = now.toString();
    localStorage.setItem(firstVisitKey, firstVisit);
    return; // Don't show popup on first visit of new session
  }

  // Check if 2 minutes have passed since first visit
  const timeSinceFirstVisit = now - parseInt(firstVisit);
  if (timeSinceFirstVisit < 2 * 60 * 1000) {
    // 2 minutes in milliseconds
    return;
  }

  // If we're here, it's been 2+ minutes since first visit in this session
  (async () => {
    try {
      const response = await fetch("/api/support-count", {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const popup = document.getElementById("coffee-popup");
      const countElement = document.getElementById("support-count");
      const loadingElement = popup.querySelector(".loading-count");

      if (countElement && loadingElement) {
        countElement.textContent = data.count;
        countElement.style.display = "inline";
        loadingElement.style.display = "none";
      }

      popup.classList.remove("hidden");
      localStorage.setItem(popupKey, now.toString());
    } catch (err) {
      console.error("Failed to show support popup:", err);
    }
  })();
}

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const username = urlParams.get("username");
  if (username) {
    initSupportPopup(username);
  }
});
