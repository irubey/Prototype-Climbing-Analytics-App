document.addEventListener("mousemove", function(event) {
    var x = event.clientX;
    var y = event.clientY;

    var loadingText = document.getElementById("loadingText");
    if (loadingText) {  // Only move it if it exists
        loadingText.style.left = x + "px";
        loadingText.style.top = y + "px";
    }
});

function showLoadingScreen() {
    document.getElementById("loadingScreen").style.display = "block";
}

