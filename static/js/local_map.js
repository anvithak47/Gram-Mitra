(function () {
  let map = null;
  let analysisCircle = null;
  let userMarker = null;
  let businessMarkers = [];

  let currentRadius = 8;
  let currentCoords = null;

  function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
      element.textContent = value;
    }
  }

  function formatDistance(distance) {
    const value = Number(distance);

    if (!Number.isFinite(value)) {
      return "—";
    }

    return `${value.toFixed(1)} km`;
  }

  // Remove only old similar-business markers
  function clearBusinessMarkers() {
    businessMarkers.forEach((marker) => {
      if (map && map.hasLayer(marker)) {
        map.removeLayer(marker);
      }
    });

    businessMarkers = [];
  }

  // Create / update the map
  function initMap(latitude, longitude) {
    const lat = Number(latitude);
    const lon = Number(longitude);

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      console.error("Invalid map coordinates:", latitude, longitude);
      return false;
    }

    currentCoords = {
      lat: lat,
      lon: lon,
    };

    if (!map) {
      map = L.map("businessMap").setView(
        [lat, lon],
        12
      );

      L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
          maxZoom: 19,
          attribution: "© OpenStreetMap contributors",
        }
      ).addTo(map);
    } else {
      map.setView([lat, lon], 12);
    }

    // Remove previous user marker
    if (userMarker && map.hasLayer(userMarker)) {
      map.removeLayer(userMarker);
    }

    // Remove previous analysis circle
    if (
      analysisCircle &&
      map.hasLayer(analysisCircle)
    ) {
      map.removeLayer(analysisCircle);
    }

    /*
      USER / PROPOSED BUSINESS LOCATION
    */

    userMarker = L.marker([lat, lon])
      .addTo(map)
      .bindPopup(
        "<b>📍 Your Proposed Business Location</b>"
      );

    /*
      ANALYSIS RADIUS CIRCLE

      This is the important part that visually
      displays the selected analysis area.
    */

    analysisCircle = L.circle(
      [lat, lon],
      {
        radius: currentRadius * 1000,

        color: "#ef4444",

        weight: 2,

        fillColor: "#ef4444",

        fillOpacity: 0.18,
      }
    ).addTo(map);

    // Keep the circle behind markers
    analysisCircle.bringToBack();

    // Force Leaflet to redraw
    setTimeout(() => {
      map.invalidateSize();
    }, 300);

    return true;
  }

  function getCompetitionLabel(level) {
    if (!level) {
      return "—";
    }

    const normalized =
      String(level).toLowerCase();

    if (normalized === "low") {
      return "🟢 Low";
    }

    if (normalized === "moderate") {
      return "🟡 Moderate";
    }

    if (normalized === "high") {
      return "🔴 High";
    }

    return level;
  }

  /*
    CREATE A RED MARKER FOR SIMILAR BUSINESSES
  */

  function createBusinessMarker(
    latitude,
    longitude,
    business,
    index
  ) {
    const redIcon = L.divIcon({
      className: "similar-business-marker",

      html: `
        <div style="
          width: 18px;
          height: 18px;
          background: #ef4444;
          border: 3px solid white;
          border-radius: 50%;
          box-shadow: 0 2px 6px rgba(0,0,0,0.4);
        "></div>
      `,

      iconSize: [18, 18],

      iconAnchor: [9, 9],

      popupAnchor: [0, -10],
    });

    const marker = L.marker(
      [latitude, longitude],
      {
        icon: redIcon,
      }
    )
      .addTo(map)
      .bindPopup(`
        <div style="min-width:180px">
          <b>${business.name || "Similar Business"}</b>
          <br><br>

          📌 Type:
          ${business.type || "Business"}

          <br>

          📏 Distance:
          ${formatDistance(
            business.distance_km
          )}

          <br>

          🏆 Nearest Rank:
          #${index + 1}
        </div>
      `);

    businessMarkers.push(marker);

    return marker;
  }

  /*
    LOAD SIMILAR BUSINESSES
  */

  async function loadBusinesses() {
    if (!map || !currentCoords) {
      console.error(
        "Map or coordinates are not ready"
      );
      return;
    }

    let reportData = {};

    try {
      reportData = JSON.parse(
        localStorage.getItem(
          "gramMitraReport"
        ) || "{}"
      );
    } catch (error) {
      console.error(
        "Unable to read report data:",
        error
      );
    }

    setText(
      "mapSummary",
      `Finding similar businesses within ${currentRadius} km...`
    );

    try {
      const response = await fetch(
        "/api/nearby-businesses",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            latitude: currentCoords.lat,

            longitude: currentCoords.lon,

            radius: currentRadius,

            category:
              reportData.category ||
              "Retail & Services",

            business_idea:
              reportData.business_idea || "",
          }),
        }
      );

      const data = await response.json();

      console.log(
        "Nearby business API response:",
        data
      );

      // Remove previous business markers
      clearBusinessMarkers();

      /*
        UPDATE ANALYSIS CIRCLE
      */

      if (analysisCircle) {
        analysisCircle.setLatLng(
          [
            currentCoords.lat,
            currentCoords.lon,
          ]
        );

        analysisCircle.setRadius(
          currentRadius * 1000
        );

        analysisCircle.bringToBack();
      }

      /*
        UPDATE STATISTICS
      */

      const businesses =
        Array.isArray(data.places)
          ? data.places
          : [];

      setText(
        "similarCount",
        String(data.count ?? businesses.length)
      );

      setText(
        "mapCompetitionLevel",
        getCompetitionLabel(
          data.competition_level
        )
      );

      if (businesses.length > 0) {
        const nearest = businesses[0];

        setText(
          "nearestDistance",
          `${nearest.name || "Business"} (${formatDistance(
            nearest.distance_km
          )})`
        );
      } else {
        setText(
          "nearestDistance",
          "No similar business found"
        );
      }

      /*
        CHECK API AVAILABILITY
      */

      if (!data.available) {
        setText(
          "mapSummary",
          data.error ||
            "Nearby business data is unavailable."
        );

        return;
      }

      /*
        CREATE MAP BOUNDS

        Starts with the user's location.
      */

      const bounds = L.latLngBounds();

      bounds.extend([
        currentCoords.lat,
        currentCoords.lon,
      ]);

      /*
        ADD RED SIMILAR-BUSINESS MARKERS
      */

      let validMarkerCount = 0;

      businesses.forEach(
        (business, index) => {
          /*
            IMPORTANT:

            Supports multiple possible coordinate
            names returned by your backend.
          */

          const businessLat =
            Number(
              business.lat ??
              business.latitude
            );

          const businessLon =
            Number(
              business.lon ??
              business.lng ??
              business.longitude
            );

          // Skip invalid businesses
          if (
            !Number.isFinite(businessLat) ||
            !Number.isFinite(businessLon)
          ) {
            console.warn(
              "Invalid business coordinates:",
              business
            );

            return;
          }

          createBusinessMarker(
            businessLat,
            businessLon,
            business,
            index
          );

          bounds.extend([
            businessLat,
            businessLon,
          ]);

          validMarkerCount++;
        }
      );

      /*
        UPDATE MAP SUMMARY
      */

      const businessCount = data.count ?? businesses.length;

if (businessCount === 0) {
  setText(
    "mapSummary",
    `No similar businesses were found within ${currentRadius} km.`
  );
} else {
  setText(
    "mapSummary",
    `${businessCount} similar business${
      businessCount === 1 ? "" : "es"
    } found within ${currentRadius} km.`
  );
}

      /*
        FIT MAP

        Only fit to business markers if valid
        coordinates exist.
      */

      if (validMarkerCount > 0) {
        map.fitBounds(bounds, {
          padding: [50, 50],
          maxZoom: 14,
        });
      } else {
        /*
          Even if markers fail,
          the analysis circle remains visible.
        */

        map.setView(
          [
            currentCoords.lat,
            currentCoords.lon,
          ],
          12
        );
      }

      /*
        IMPORTANT:

        Force redraw after all layers
        have been added.
      */

      setTimeout(() => {
        map.invalidateSize();

        if (analysisCircle) {
          analysisCircle.bringToBack();
        }

        if (userMarker) {
          userMarker.bringToFront();
        }

        businessMarkers.forEach(
          (marker) => {
            marker.bringToFront();
          }
        );
      }, 500);

    } catch (error) {
      console.error(
        "Error loading nearby businesses:",
        error
      );

      setText(
        "mapSummary",
        "Could not load nearby business data."
      );
    }
  }

  /*
    RESOLVE USER LOCATION
  */

  async function resolveCoordinates(
    reportData
  ) {
    const location =
      reportData.location || {};

    const latitude = Number(
      location.latitude ??
      reportData.latitude
    );

    const longitude = Number(
      location.longitude ??
      reportData.longitude
    );

    /*
      CASE 1:
      Coordinates already exist
    */

    if (
      Number.isFinite(latitude) &&
      Number.isFinite(longitude)
    ) {
      return initMap(
        latitude,
        longitude
      );
    }

    /*
      CASE 2:
      Use existing geocoding API
    */

    try {
      const response = await fetch(
        "/api/geocode",
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            village:
              location.village ||
              reportData.village ||
              "",

            taluk:
              location.taluk ||
              reportData.taluk ||
              "",

            district:
              location.district ||
              reportData.district ||
              "",
          }),
        }
      );

      const data =
        await response.json();

      if (data.found) {
        return initMap(
          data.latitude,
          data.longitude
        );
      }

    } catch (error) {
      console.error(
        "Geocoding failed:",
        error
      );
    }

    setText(
      "mapSummary",
      "Location coordinates are unavailable."
    );

    return false;
  }

  /*
    START MAP
  */

  async function boot() {
    const section =
      document.getElementById(
        "competitionMapSection"
      );

    const mapElement =
      document.getElementById(
        "businessMap"
      );

    if (
      !section ||
      !mapElement ||
      typeof L === "undefined"
    ) {
      console.error(
        "Map section, map container, or Leaflet is missing."
      );

      return;
    }

    let reportData = null;

    try {
      reportData = JSON.parse(
        localStorage.getItem(
          "gramMitraReport"
        ) || "null"
      );
    } catch (error) {
      console.error(
        "Could not read Gram Mitra report:",
        error
      );
    }

    if (!reportData) {
      console.warn(
        "No Gram Mitra report data found."
      );

      return;
    }

    const coordinatesFound =
      await resolveCoordinates(
        reportData
      );

    if (!coordinatesFound) {
      return;
    }

    /*
      RADIUS BUTTONS
    */

    document
      .querySelectorAll(
        ".radius-btn"
      )
      .forEach((button) => {
        button.addEventListener(
          "click",
          () => {
            document
              .querySelectorAll(
                ".radius-btn"
              )
              .forEach((item) => {
                item.classList.remove(
                  "active"
                );
              });

            button.classList.add(
              "active"
            );

            currentRadius =
              Number(
                button.dataset.radius
              ) || 8;

            /*
              Immediately update
              the visible circle.
            */

            if (analysisCircle) {
              analysisCircle.setRadius(
                currentRadius * 1000
              );

              analysisCircle.bringToBack();
            }

            /*
              Reload businesses
              for the new radius.
            */

            loadBusinesses();
          }
        );
      });

    /*
      INITIAL LOAD
    */

    await loadBusinesses();

    /*
      FINAL MAP REFRESH
    */

    setTimeout(() => {
      if (map) {
        map.invalidateSize();
      }
    }, 800);
  }

  document.addEventListener(
    "DOMContentLoaded",
    boot
  );
})();