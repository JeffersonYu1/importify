// JavaScript for the "import by" pages

// Change div display based on Destination Selector
$(document).ready(function(){
    $('input[name="destinationRadioOption"]').on('change', function(){
        var n = $(this).val();
        switch(n)
        {
                case '0':
                    $('#newPlaylistForm').css("display", "inline");
                    $('#existingPlaylistForm').css("display", "none");
                    break;
                case '1':
                    $('#newPlaylistForm').css("display", "none");
                    $('#existingPlaylistForm').css("display", "inline");
                    break;
            }
    });

    $("#importBySubmit").click(function() {
        let valid = true;

        // Validate Spotify URL
        if($("#playlist_link").length && $("#playlist_link").val().lastIndexOf("https://open.spotify.com/playlist/", 0) !== 0)
        {
            valid = false;
            $("#error_message").html("Invalid playlist URL.");
            $("#error_message").css("display", "inline");
            return;
        }        
        
        // If destination is selected as existing playlist, validate playlist
        if($('input[name="destinationRadioOption"]:checked').val() == 1 && $('#existingPlaylistForm option:selected').val() == 'none') 
        {
            valid = false;
            $("#error_message").html("No destination playlist selected.");
            $("#error_message").css("display", "inline");
            return;
        }

        if($('#playlist_paste').length && $('#playlist_paste').val().trim() == "")
        {
            valid = false;
            $("#error_message").html("Source is empty or invalid.");
            $("#error_message").css("display", "inline");
            return;
        }
        
        if(valid) {
            $("#importBy").submit();
        }
    });
});

