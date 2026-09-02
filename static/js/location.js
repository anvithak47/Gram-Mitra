let locationData = {};

async function initLocations() {
  const district = document.getElementById("district"); 
  if (!district) return;
  
  try {
    const res = await fetch("/api/locations");
    if (!res.ok) throw new Error("Locations endpoint unavailable");
    locationData = await res.json();
    
    // Reset district options while preserving the default placeholder
    district.innerHTML = '<option value="" disabled selected data-i18n="select_district">' + 
      (typeof t === 'function' ? t('select_district') : 'Select district') + '</option>';
    
    Object.keys(locationData).sort().forEach(d => {
      if (d !== "Karnataka") { // Excludes 'Karnataka' if returned as a top-level key
        district.add(new Option(d, d));
      }
    });
    
    district.selectedIndex = 0; // Keeps 'Select district' highlighted on page load
  } catch (err) {
    console.warn("Could not load location hierarchy from API:", err);
  }

  district.addEventListener("change", () => {
    const taluk = document.getElementById("taluk");
    if (!taluk) return;
    taluk.innerHTML = '<option value="" disabled selected data-i18n="select_taluk">' + 
      (typeof t === 'function' ? t('select_taluk') : 'Select taluk') + '</option>';
    
    const talukList = locationData[district.value] || [];
    talukList.forEach(tName => taluk.add(new Option(tName, tName)));
  });

  const liveBtn = document.getElementById("liveLocation") || document.getElementById("useLocationBtn");
  if (liveBtn) {
    liveBtn.addEventListener("click", useLocation);
  }
}

function useLocation() {
  const status = document.getElementById("locationStatus") || document.getElementById("detectedAddress");
  const helperText = typeof t === 'function' ? t : (k) => k;

  if (status) status.textContent = helperText("location_requesting") || "Requesting location...";
  
  if (!navigator.geolocation) {
    if (status) status.textContent = helperText("location_unsupported") || "Geolocation unsupported.";
    return;
  }

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const { latitude, longitude } = pos.coords;
      
      // Save coordinates to localStorage
      localStorage.setItem("gramMitraCoordinates", JSON.stringify({ latitude, longitude }));
      
      const addrElem = document.getElementById("address") || document.getElementById("detectedAddress");
      if (addrElem) {
        addrElem.value = `GPS: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
      }

      const latElem = document.getElementById("latitude");
      const lngElem = document.getElementById("longitude");
      if (latElem) latElem.value = latitude;
      if (lngElem) lngElem.value = longitude;

      // Reverse geocode lat/lng to actual address string using OpenStreetMap
      try {
        const geoRes = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`);
        const geoData = await geoRes.json();
        if (geoData && geoData.display_name && addrElem) {
          addrElem.value = geoData.display_name;
        }
      } catch (e) {
        // Fallback remains the GPS coordinates set above
      }

      if (status && status !== addrElem) {
        status.textContent = `${helperText("location_received") || "Location set"}: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
      }
    },
    (err) => {
      if (status) status.textContent = helperText("location_failed") || "Location access denied.";
      alert("Unable to fetch location. Please ensure location permissions are granted in your browser address bar.");
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

document.addEventListener("DOMContentLoaded", initLocations);