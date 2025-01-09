// Projects Table functionality

function getProjectsData(userTicks, minBinnedGrade, discipline, timeRange) {
  // Filter for unclimbed routes at or above min grade
  const routeAttempts = new Map(); // Map to store attempts per route

  userTicks.forEach((tick) => {
    // Apply discipline filter
    if (discipline !== "all" && tick.discipline !== discipline) return;

    // Apply time range filter
    const tickDate = new Date(tick.tick_date);
    const now = new Date();
    if (
      timeRange === "lastYear" &&
      tickDate < new Date(now.setFullYear(now.getFullYear() - 1))
    )
      return;
    if (
      timeRange === "lastSixMonths" &&
      tickDate < new Date(now.setMonth(now.getMonth() - 6))
    )
      return;

    // Check grade requirement
    if (!tick.binned_code || tick.binned_code < minBinnedGrade) return;

    const routeKey = `${tick.route_name}|${tick.location}|${tick.route_url}`;

    if (!routeAttempts.has(routeKey)) {
      routeAttempts.set(routeKey, {
        name: tick.route_name,
        location: tick.location,
        route_grade: tick.route_grade,
        binned_grade: tick.binned_grade,
        binned_code: tick.binned_code,
        route_url: tick.route_url,
        attempts: [],
        hasSent: false,
        season_category: tick.season_category,
        length_category: tick.length_category,
        notes: [], // Initialize notes array
      });
    }

    const routeData = routeAttempts.get(routeKey);
    // Ensure we have a valid date string
    const attemptDate = tick.tick_date ? new Date(tick.tick_date) : new Date();
    routeData.attempts.push({
      date: attemptDate,
      send: tick.send_bool,
      season_category: tick.season_category,
      pitches: tick.pitches || 1,
      length_category: tick.length_category,
      notes: tick.notes, // Store notes with each attempt
    });

    // Store notes if they exist
    if (tick.notes) {
      routeData.notes.push({
        date: attemptDate,
        text: tick.notes,
      });
    }

    // Update season_category if this attempt is more recent
    if (attemptDate > Math.max(...routeData.attempts.map((a) => a.date))) {
      routeData.season_category = tick.season_category;
    }

    if (tick.send_bool) {
      routeData.hasSent = true;
    }
  });

  // Filter out sent routes and process attempt data
  const projects = Array.from(routeAttempts.values())
    .filter((route) => !route.hasSent)
    .map((route) => {
      // Get unique dates by converting to date strings in YYYY-MM-DD format
      const uniqueDates = new Set(
        route.attempts.map((a) => a.date.toISOString().split("T")[0])
      );

      // Sort notes by date
      const sortedNotes = route.notes
        .sort((a, b) => b.date - a.date)
        .map((note) => ({
          date: formatDate(note.date),
          text: note.text,
        }));

      // Calculate total attempts based on length_category
      const totalAttempts =
        route.length_category === "multipitch"
          ? route.attempts.length
          : route.attempts.reduce((sum, attempt) => sum + attempt.pitches, 0);

      return {
        name: route.name,
        location: route.location,
        route_grade: route.route_grade,
        binned_grade: route.binned_grade,
        binned_code: route.binned_code,
        route_url: route.route_url,
        daysProjected: uniqueDates.size,
        totalAttempts: totalAttempts,
        lastAttempted: new Date(Math.max(...route.attempts.map((a) => a.date))),
        season_category: route.season_category,
        length_category: route.length_category,
        notes: sortedNotes,
        hasNotes: sortedNotes.length > 0,
      };
    })
    .sort((a, b) => {
      // Sort by binned grade (desc) then total attempts (desc)
      if (b.binned_code !== a.binned_code) {
        return b.binned_code - a.binned_code;
      }
      return b.totalAttempts - a.totalAttempts;
    })
    .slice(0, 100); // Limit to 100 routes

  return projects;
}

function formatDate(date) {
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function updateProjectsTable(projects) {
  const tbody = document.querySelector("#projects-table tbody");
  tbody.innerHTML = ""; // Clear existing content

  // Group projects by binned grade code
  const projectsByGrade = projects.reduce((acc, project) => {
    if (!acc[project.binned_code]) {
      acc[project.binned_code] = {
        grade: project.binned_grade,
        projects: [],
      };
    }
    acc[project.binned_code].projects.push(project);
    return acc;
  }, {});

  // Sort by binned grade code (descending) and render each group
  Object.entries(projectsByGrade)
    .sort(([a], [b]) => Number(b) - Number(a))
    .forEach(([binned_code, { grade, projects: gradeProjects }]) => {
      // Add grade header row
      const headerRow = document.createElement("tr");
      headerRow.className = "grade-header";
      headerRow.innerHTML = `
        <td colspan="7">${grade}</td>
      `;
      tbody.appendChild(headerRow);

      // Sort projects within grade by total attempts
      gradeProjects
        .sort((a, b) => b.totalAttempts - a.totalAttempts)
        .forEach((project) => {
          const row = document.createElement("tr");
          const notesButton = project.hasNotes
            ? `<button onclick="showProjectNotes('${encodeURIComponent(
                JSON.stringify(project)
              )}')" class="notes-btn">
              <i class="fas fa-sticky-note"></i>
            </button>`
            : "";

          row.innerHTML = `
            <td>
              <a href="${project.route_url}" target="_blank">${project.name}</a>
              ${notesButton}
            </td>
            <td>${project.route_grade}</td>
            <td>${project.location}</td>
            <td>${project.daysProjected}</td>
            <td>${project.totalAttempts}</td>
            <td>${project.season_category}</td>
          `;
          tbody.appendChild(row);
        });
    });
}

// Add notes modal functionality
window.showProjectNotes = function (projectJson) {
  const project = JSON.parse(decodeURIComponent(projectJson));
  const modal = document.getElementById("notesModal") || createNotesModal();

  const content = modal.querySelector(".modal-content");
  content.innerHTML = `
    <div class="modal-section">
      <h3>${project.name} - ${project.route_grade}</h3>
      <span class="modal-close">&times;</span>
      ${project.notes
        .map(
          (note) => `
        <div class="modal-section">
          <h4>${note.date}</h4>
          <p>${note.text}</p>
        </div>
      `
        )
        .join("")}
    </div>
  `;

  // Add event listeners
  modal.querySelector(".modal-close").onclick = () =>
    (modal.style.display = "none");
  window.onclick = (event) => {
    if (event.target === modal) modal.style.display = "none";
  };

  modal.style.display = "block";
};

function createNotesModal() {
  const modal = document.createElement("div");
  modal.id = "notesModal";
  modal.className = "modal";
  modal.innerHTML = '<div class="modal-content"></div>';
  document.body.appendChild(modal);
  return modal;
}

// Add to window load event
window.addEventListener("load", function () {
  // Add modal functionality
  window.openProjectsModal = function () {
    document.getElementById("projectsModal").style.display = "block";
  };

  window.closeProjectsModal = function () {
    document.getElementById("projectsModal").style.display = "none";
  };

  // Update projects table when filters change
  function updateProjects() {
    const discipline = document.querySelector(
      'input[name="performance-pyramid-discipline-filter"]:checked'
    ).value;
    const timeRange = document.querySelector(
      'input[name="performance-pyramid-time-filter"]:checked'
    ).value;

    // Get min grade from pyramid data based on discipline
    let pyramidData;
    switch (discipline) {
      case "sport":
        pyramidData = sportPyramidData;
        break;
      case "trad":
        pyramidData = tradPyramidData;
        break;
      case "boulder":
        pyramidData = boulderPyramidData;
        break;
      default:
        pyramidData = sportPyramidData;
    }

    // Get min grade, ensuring we have valid data
    let minBinnedGrade;
    if (pyramidData && pyramidData.length > 0) {
      const validGrades = pyramidData
        .filter((d) => typeof d.binned_code === "number")
        .map((d) => d.binned_code);

      if (validGrades.length > 0) {
        minBinnedGrade = Math.min(...validGrades); // Use min from pyramid data
      } else {
        minBinnedGrade = 0;
      }
    } else {
      minBinnedGrade = 0;
    }

    const projects = getProjectsData(
      userTicksData,
      minBinnedGrade,
      discipline,
      timeRange
    );
    updateProjectsTable(projects);
  }

  // Add filter change listeners
  document
    .querySelectorAll(
      'input[name="performance-pyramid-discipline-filter"], input[name="performance-pyramid-time-filter"]'
    )
    .forEach((input) => {
      input.addEventListener("change", updateProjects);
    });

  // Initial update
  updateProjects();
});
