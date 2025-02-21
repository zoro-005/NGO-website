var google;

function init() {
    var myLatlng = new google.maps.LatLng(29.038186193921526, 77.71798811534256);
    
    var mapOptions = {
        zoom: 7,
        center: myLatlng,
        scrollwheel: false,
        styles: [{
            "featureType": "administrative.country",
            "elementType": "geometry",
            "stylers": [
                {"visibility": "simplified"},
                {"hue": "#ff0000"}
            ]
        }]
    };

    var mapElement = document.getElementById('map');
    var map = new google.maps.Map(mapElement, mapOptions);
    
    var addresses = ['Meerut'];

    for (var x = 0; x < addresses.length; x++) {
        $.getJSON('https://maps.googleapis.com/maps/api/geocode/json?address=' + 
            addresses[x] + '&key=YOUR_API_KEY', null, function(data) {
            if (data.results && data.results[0]) {
                var p = data.results[0].geometry.location;
                var latlng = new google.maps.LatLng(p.lat, p.lng);
                new google.maps.Marker({
                    position: latlng,
                    map: map,
                    icon: 'images/loc.png'
                });
            } else {
                console.log('Geocoding failed for address: ' + addresses[x]);
            }
        }).fail(function() {
            console.log('Geocoding request failed');
        });
    }
}

google.maps.event.addDomListener(window, 'load', init);