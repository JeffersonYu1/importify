// JavaScript for the "import by" pages

// Change div display based on Destination Selector
$(document).ready(function(){
    $('input[name=destinationRadioOption]').on('change', function(){
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
});