function loading_message()
{
    message = document.querySelector("#display_message");
    message.innerHTML = "Playlists with more than 100 songs may have longer loading times.&#10;Thanks for your patience :)";
    message.style.display = "inline";
}