// User management utilities
const USER_KEY = "current_climbing_user";

/**
 * Stores the current username in localStorage.
 * @param {string} username - The username to store.
 */
function setCurrentUser(username) {
  localStorage.setItem(USER_KEY, username);
}

/**
 * Retrieves the current username from localStorage.
 * @returns {string|null} The stored username or null if not set.
 */
function getCurrentUser() {
  return localStorage.getItem(USER_KEY);
}

/**
 * Clears the stored username from localStorage.
 */
function clearCurrentUser() {
  localStorage.removeItem(USER_KEY);
}

/**
 * Validates that the username in the URL matches the stored username.
 * If there's a mismatch, redirects to the correct user's page.
 */
function validateUserContext() {
  const currentUser = getCurrentUser();
  const urlParams = new URLSearchParams(window.location.search);
  const urlUsername = urlParams.get("username");

  if (currentUser && urlUsername && currentUser !== urlUsername) {
    // Redirect to the correct user's page
    window.location.href = `${window.location.pathname}?username=${currentUser}`;
  }
}

/**
 * Clears the stored username if the current path is the index page.
 */
function handleIndexPage() {
  if (window.location.pathname === "/") {
    clearCurrentUser();
  }
}

/**
 * Initializes user validation and index page handling on page load.
 */
document.addEventListener("DOMContentLoaded", function () {
  handleIndexPage();
  validateUserContext();
});

/**
 * Clears the stored username based on custom headers.
 * To be invoked manually if needed.
 * Alternatively, implement additional logic to handle headers if using fetch globally.
 */
function clearUserIfRequired(response) {
  if (response.headers.get("X-Clear-User") === "true") {
    clearCurrentUser();
  }
}
