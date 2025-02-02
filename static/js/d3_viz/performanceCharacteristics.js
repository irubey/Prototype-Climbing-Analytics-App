// Data Management Layer
const DataManager = {
  initialized: false,
  data: {
    sport: null,
    trad: null,
    boulder: null,
    binnedCodes: null
  },

  init() {
    try {
      console.log('DataManager init - Starting initialization');
      console.log('DataManager init - Window data availability:', {
        sportPyramidData: typeof window.sportPyramidData !== 'undefined',
        tradPyramidData: typeof window.tradPyramidData !== 'undefined',
        boulderPyramidData: typeof window.boulderPyramidData !== 'undefined',
        binnedCodeDict: typeof window.binnedCodeDict !== 'undefined'
      });

      this.data = {
        sport: window.sportPyramidData || [],
        trad: window.tradPyramidData || [],
        boulder: window.boulderPyramidData || [],
        binnedCodes: window.binnedCodeDict || []
      };

      console.log('DataManager init - Data after assignment:', {
        sport: {
          type: typeof this.data.sport,
          isArray: Array.isArray(this.data.sport),
          length: this.data.sport?.length,
          sample: this.data.sport?.[0]
        },
        trad: {
          type: typeof this.data.trad,
          isArray: Array.isArray(this.data.trad),
          length: this.data.trad?.length,
          sample: this.data.trad?.[0]
        },
        boulder: {
          type: typeof this.data.boulder,
          isArray: Array.isArray(this.data.boulder),
          length: this.data.boulder?.length,
          sample: this.data.boulder?.[0]
        },
        binnedCodes: {
          type: typeof this.data.binnedCodes,
          isArray: Array.isArray(this.data.binnedCodes),
          length: this.data.binnedCodes?.length,
          sample: this.data.binnedCodes?.[0]
        }
      });

      // Validate data structure
      if (!this.validateData()) {
        console.error('DataManager init - Data validation failed');
        throw new Error('Invalid data structure');
      }

      console.log('DataManager init - Initialization successful');
      this.initialized = true;
      return true;
    } catch (error) {
      console.error('DataManager init - Initialization failed:', error);
      this.showError('Failed to initialize visualization data');
      return false;
    }
  },

  validateData() {
    return Array.isArray(this.data.sport) &&
      Array.isArray(this.data.trad) &&
      Array.isArray(this.data.boulder) &&
      Array.isArray(this.data.binnedCodes);
  },

  showError(message) {
    const container = document.querySelector('#performance-characteristics');
    if (container) {
      container.innerHTML = `
        <div class="alert alert-warning">
          ${message}
          <button onclick="location.reload()">Retry</button>
        </div>`;
    }
  }
};

// Define colors at the top level
const colors = {
  primary: {
    fill: "#3498db",
    stroke: "#2980b9",
  },
  secondary: {
    fill: "#e74c3c",
    stroke: "#c0392b",
  },
  text: {
    dark: "#2c3e50",
    light: "#7f8c8d",
    highlight: "#2980b9",
  },
  length: {
    short: "#2ecc71",
    medium: "#3498db",
    long: "#9b59b6",
    multipitch: "#e74c3c"
  },
};

// Check if all required functions are loaded
function checkRequiredFunctions() {
  const requiredFunctions = [
    'getGradeForCode',
    'setupChart',
    'processData',
    'processCategory',
    'createTooltip',
    'positionTooltip',
    'showTooltip',
    'hideTooltip',
    'handleBarHover',
    'handleBarUnhover',
    'handleBarClick',
    'drawMissingDataMessage',
    'drawBarsAndAxes',
    'characteristicsVizChart'
  ];

  const missingFunctions = requiredFunctions.filter(
    func => typeof window[func] !== 'function'
  );

  if (missingFunctions.length > 0) {
    console.error('Missing required functions:', missingFunctions);
    return false;
  }
  return true;
}

// Make all required functions globally accessible
window.getGradeForCode = function (binnedCode, binnedCodeDict) {
  const entry = binnedCodeDict.find((item) => item.binned_code === binnedCode);
  return entry ? entry.binned_grade : binnedCode;
};

window.setupChart = function (targetId) {
  // Calculate dimensions based on container width
  const container = d3.select(targetId).node().getBoundingClientRect();
  const margin = { top: 40, right: 120, bottom: 80, left: 60 };
  const width = Math.min(container.width - margin.left - margin.right, 900);
  const height = width * 0.5;

  const svg = d3
    .select(targetId)
    .append("svg")
    .attr("width", "100%")
    .attr("height", height + margin.top + margin.bottom)
    .attr(
      "viewBox",
      `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`
    )
    .attr("preserveAspectRatio", "xMidYMid meet");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Use a more distinct color palette
  const z = d3.scaleOrdinal().range([
    "#DB784D", // Terracotta
    "#F3B562", // Gold
    "#7CB9A8", // Sage
    "#5B8BA0", // Blue
  ]);

  const x = d3.scaleBand().rangeRound([0, width]).paddingInner(0.05).align(0.1);
  const y = d3.scaleLinear().rangeRound([height, 0]);

  return { svg, g, x, y, z, width, height, margin };
};

window.processData = function (data, keys) {
  // Process data for all three categories
  const energyData = data.some(d => d.crux_energy)
    ? processCategory(data, "crux_energy", ["Power", "Power_Endurance", "Endurance", "Technique"], keys)
    : [{ category: "missing-data", total: 0, routesByGrade: {} }];

  const lengthData = processCategory(data, "length_category", ["short", "medium", "long", "multipitch"], keys);

  const angleData = data.some(d => d.crux_angle)
    ? processCategory(data, "crux_angle", ["Slab", "Vertical", "Overhang", "Roof"], keys)
    : [{ category: "missing-data", total: 0, routesByGrade: {} }];

  return [
    { group: "Energy System", data: energyData, hasMissingData: !data.some(d => d.crux_energy) },
    { group: "Length", data: lengthData, hasMissingData: !data.some(d => d.length_category) },
    { group: "Angle", data: angleData, hasMissingData: !data.some(d => d.crux_angle) }
  ];
};

window.processCategory = function (data, attribute, validValues, keys) {
  const groupedData = d3.group(data, d => d[attribute] || "Unknown");
  return Array.from(groupedData, ([key, values]) => {
    const counts = {};
    const routesByGrade = {};

    // Initialize counts for all possible keys to 0
    keys.forEach(k => {
      counts[k] = 0;
    });

    values.forEach(v => {
      if (v.binned_code) {
        counts[v.binned_code] = (counts[v.binned_code] || 0) + 1;
        if (!routesByGrade[v.binned_code]) {
          routesByGrade[v.binned_code] = [];
        }
        routesByGrade[v.binned_code].push({
          name: v.route_name,
          date: v.tick_date,
          grade: v.route_grade,
          location: v.location,
          attempts: v.num_attempts
        });
      }
    });

    return {
      category: key,
      ...counts,
      routesByGrade,
      total: values.length
    };
  })
    .filter(d => validValues.includes(d.category))
    .sort((a, b) => b.total - a.total);
};

window.createTooltip = function () {
  return d3
    .select("body")
    .append("div")
    .attr("class", "d3-tooltip")
    .style("position", "absolute")
    .style("visibility", "hidden")
    .style("background-color", "white")
    .style("border", "1px solid #ddd")
    .style("border-radius", "4px")
    .style("padding", "10px")
    .style("font-size", "12px")
    .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)")
    .style("max-width", "300px")
    .style("max-height", "400px")
    .style("overflow-y", "auto")
    .style("z-index", "1000");
};

window.positionTooltip = function (event, tooltip) {
  const tooltipNode = tooltip.node();
  const tooltipRect = tooltipNode.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  let left = event.pageX + 10;
  let top = event.pageY - 10;

  if (left + tooltipRect.width > viewportWidth - 10) {
    left = event.pageX - tooltipRect.width - 10;
  }
  if (top + tooltipRect.height > viewportHeight - 10) {
    top = event.pageY - tooltipRect.height - 10;
  }
  if (top < 10) {
    top = 10;
  }
  if (left < 10) {
    left = 10;
  }

  return { left, top };
};

window.showTooltip = function (event, d, tooltip, gradeKey, data, binnedCodeDict, isPinned = false) {
  const routes = (data.routesByGrade[gradeKey] || []).sort(
    (a, b) => new Date(b.date) - new Date(a.date)
  );
  const total = routes.length;

  let tooltipContent = `
    <div style="margin-bottom: 5px;">
      <strong>${getGradeForCode(gradeKey, binnedCodeDict)} ${data.category}</strong>
      ${isPinned
      ? '<span style="float: right; cursor: pointer; color: #666;" class="close-btn">×</span>'
      : '<span style="float: right; font-size: 11px; color: #666;">Click to pin</span>'
    }
    </div>
    <div style="margin-bottom: 8px;">
      Total Pitches: ${total}
    </div>
    <div style="border-top: 1px solid #eee; padding-top: 5px;">
      <strong>Routes:</strong>
      ${routes
      .map(
        (route) => `
        <div style="margin-top: 3px; padding: 3px 0;">
          <div><strong>${route.name}</strong> ${route.grade}</div>
          <div style="font-size: 11px; color: #666;">
            ${route.location} • ${route.attempts === 1
            ? "Flash/Onsight"
            : `${route.attempts} attempts`
          } • ${new Date(route.date).toLocaleDateString()}
          </div>
        </div>
      `
      )
      .join("")}
    </div>
  `;

  tooltip.style("visibility", "visible").html(tooltipContent);

  if (isPinned) {
    tooltip.select(".close-btn").on("click", function () {
      d3.event.stopPropagation();
      hideTooltip(tooltip);
    });
  }

  const position = positionTooltip(event, tooltip);
  tooltip.style("left", position.left + "px").style("top", position.top + "px");
};

window.hideTooltip = function (tooltip) {
  tooltip.style("visibility", "hidden");
};

window.handleBarHover = function (element, event, d, tooltip, binnedCodeDict) {
  d3.select(element)
    .attr("opacity", 0.8)
    .attr("stroke", "#666")
    .attr("stroke-width", 1);
  showTooltip(
    event,
    d,
    tooltip,
    d3.select(element.parentNode).datum().key,
    d.data,
    binnedCodeDict
  );
};

window.handleBarUnhover = function (element, tooltip) {
  d3.select(element)
    .attr("opacity", 1)
    .attr("stroke", "#fff")
    .attr("stroke-width", 0.5);
  hideTooltip(tooltip);
};

window.handleBarClick = function (element, event, d, tooltip, binnedCodeDict, pinnedBar) {
  event.stopPropagation();

  if (pinnedBar === element) {
    pinnedBar = null;
    d3.select(element)
      .attr("opacity", 1)
      .attr("stroke", "#fff")
      .attr("stroke-width", 0.5);
    hideTooltip(tooltip);
    return;
  }

  if (pinnedBar) {
    d3.select(pinnedBar)
      .attr("opacity", 1)
      .attr("stroke", "#fff")
      .attr("stroke-width", 0.5);
  }

  pinnedBar = element;
  d3.select(element)
    .attr("opacity", 0.8)
    .attr("stroke", "#666")
    .attr("stroke-width", 1);

  showTooltip(
    event,
    d,
    tooltip,
    d3.select(element.parentNode).datum().key,
    d.data,
    binnedCodeDict,
    true
  );
};

window.drawMissingDataMessage = function (g, groupIndex, groupWidth, height, groupPadding) {
  const messageG = g.append("g")
    .attr("transform", `translate(${groupIndex * groupWidth + groupPadding / 2}, ${height / 2 - 20})`);

  const buttonG = messageG.append("g")
    .style("cursor", "pointer")
    .on("click", () => {
      window.location.href = "/pyramid-input";
    });

  buttonG.append("rect")
    .attr("x", (groupWidth - groupPadding) / 2 - 40)
    .attr("y", 0)
    .attr("width", 80)
    .attr("height", 30)
    .attr("rx", 4)
    .attr("fill", "#6cb2eb");

  buttonG.append("text")
    .attr("x", (groupWidth - groupPadding) / 2)
    .attr("y", 20)
    .attr("text-anchor", "middle")
    .style("fill", "white")
    .style("font-size", "12px")
    .text("Add Data");
};

// Make functions globally accessible
window.characteristicsVizChart = function (targetId, pyramidData, binnedCodeDict) {
  // Clear existing chart
  d3.select(targetId).select("svg").remove();

  // Get current filters
  const discipline = d3.select("input[name='characteristics-discipline-filter']:checked").node().value;
  const timeRange = d3.select("input[name='characteristics-time-filter']:checked").node().value;

  // Extract and filter data
  if (!Array.isArray(pyramidData)) {
    console.error("Invalid pyramid data:", pyramidData);
    return;
  }

  // Filter data based on time range
  const filteredData = pyramidData.filter(d => {
    if (!d.send_date) return false;
    const sendDate = new Date(d.send_date);
    const cutoffDate = new Date();

    switch (timeRange) {
      case "lastYear":
        cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
        break;
      case "lastSixMonths":
        cutoffDate.setMonth(cutoffDate.getMonth() - 6);
        break;
      case "lastThreeMonths":
        cutoffDate.setMonth(cutoffDate.getMonth() - 3);
        break;
      default: // "allTime"
        return true;
    }
    return sendDate >= cutoffDate;
  });

  // Get unique binned codes for the legend
  let uniqueBinnedCodes = [...new Set(filteredData.map(item => item.binned_code))].filter(Boolean);
  let filteredBinnedCodeDict = binnedCodeDict.filter(entry =>
    uniqueBinnedCodes.includes(entry.binned_code)
  );
  const keys = filteredBinnedCodeDict.map(d => d.binned_code);

  // Process data
  const processedData = processData(filteredData, keys);
  if (!processedData) {
    console.error("No data to display");
    return;
  }

  // Setup chart
  const { svg, g, x, y, z, width, height, margin } = setupChart(targetId);

  // Draw visualization
  drawBarsAndAxes({
    svg,
    g,
    x,
    y,
    z,
    width,
    height,
    margin,
    dataset: processedData,
    keys,
    binnedCodeDict
  });
};

window.drawBarsAndAxes = function ({ svg, g, x, y, z, width, height, margin, dataset, keys, binnedCodeDict }) {
  const tooltip = createTooltip();
  let pinnedBar = null;

  // Ensure all data points have values for all keys
  dataset.forEach(group => {
    group.data.forEach(d => {
      keys.forEach(k => {
        if (typeof d[k] === "undefined") {
          d[k] = 0;
        }
      });
    });
  });

  // Calculate max height including stacked values
  const maxHeight = d3.max(dataset.flatMap(g =>
    g.data.map(d => keys.reduce((sum, key) => sum + (d[key] || 0), 0))
  )) || 0;

  y.domain([0, maxHeight]).nice();
  z.domain(keys);

  // Group spacing and backgrounds
  const groupWidth = width / 3;
  const groupPadding = 20;

  // Add more distinct group backgrounds
  g.selectAll(".group-background")
    .data(dataset)
    .enter()
    .append("rect")
    .attr("class", "group-background")
    .attr("x", (d, i) => i * groupWidth)
    .attr("y", -20)
    .attr("width", groupWidth - groupPadding)
    .attr("height", height + 40)
    .attr("fill", (d, i) => i % 2 === 0 ? "#f8f9fa" : "#ffffff")
    .attr("stroke", "#e9ecef")
    .attr("stroke-width", 1);

  // Draw the bars for each group or show missing data message
  dataset.forEach((group, groupIndex) => {
    if (group.hasMissingData) {
      drawMissingDataMessage(g, groupIndex, groupWidth, height, groupPadding);
      return;
    }

    const groupX = d3.scaleBand()
      .domain(group.data.map(d => d.category))
      .range([
        groupIndex * groupWidth + groupPadding / 2,
        (groupIndex + 1) * groupWidth - groupPadding / 2
      ])
      .padding(0.2);

    const bars = g.append("g")
      .selectAll("g")
      .data(d3.stack().keys(keys)(group.data))
      .enter()
      .append("g")
      .attr("fill", d => z(d.key));

    bars.selectAll("rect")
      .data(d => d)
      .enter()
      .append("rect")
      .attr("x", d => groupX(d.data.category))
      .attr("y", d => y(d[1]))
      .attr("height", d => y(d[0]) - y(d[1]))
      .attr("width", groupX.bandwidth())
      .attr("rx", 2)
      .attr("stroke", "#fff")
      .attr("stroke-width", 0.5)
      .attr("stroke-opacity", 0.8)
      .style("cursor", "pointer")
      .on("mouseover", function (event, d) {
        if (!pinnedBar) {
          handleBarHover(this, event, d, tooltip, binnedCodeDict);
        }
      })
      .on("mouseout", function () {
        if (!pinnedBar) {
          handleBarUnhover(this, tooltip);
        }
      })
      .on("click", function (event, d) {
        handleBarClick(this, event, d, tooltip, binnedCodeDict, pinnedBar);
        pinnedBar = this === pinnedBar ? null : this;
      });

    // Add labels
    g.append("g")
      .attr("class", "category-labels")
      .selectAll("text")
      .data(group.data)
      .enter()
      .append("text")
      .attr("x", d => groupX(d.category) + groupX.bandwidth() / 2)
      .attr("y", height + 15)
      .attr("text-anchor", "end")
      .attr("transform", d =>
        `rotate(-35 ${groupX(d.category) + groupX.bandwidth() / 2} ${height + 15})`
      )
      .style("font-size", "11px")
      .text(d => d.category);

    // Add group headers
    g.append("text")
      .attr("x", groupIndex * groupWidth + groupWidth / 2)
      .attr("y", -25)
      .attr("text-anchor", "middle")
      .attr("font-weight", "bold")
      .attr("font-size", "14px")
      .text(group.group);
  });

  // Add y-axis
  g.append("g")
    .attr("class", "axis")
    .call(d3.axisLeft(y).ticks(null, "s"))
    .append("text")
    .attr("x", 2)
    .attr("y", y(y.ticks().pop()) + 0.5)
    .attr("dy", "0.32em")
    .attr("fill", "#666")
    .attr("font-weight", "bold")
    .attr("text-anchor", "start")
    .text("Count");

  // Add legend
  const legend = g.append("g")
    .attr("font-family", "sans-serif")
    .attr("font-size", "11px")
    .attr("text-anchor", "start")
    .selectAll("g")
    .data(keys.slice().reverse())
    .enter()
    .append("g")
    .attr("transform", (d, i) => `translate(${width + 10},${i * 25})`);

  legend.append("rect")
    .attr("x", 0)
    .attr("width", 18)
    .attr("height", 18)
    .attr("fill", z)
    .attr("rx", 2);

  legend.append("text")
    .attr("x", 24)
    .attr("y", 9)
    .attr("dy", "0.32em")
    .style("font-size", "11px")
    .text(d => getGradeForCode(d, binnedCodeDict));

  // Add click handler to unpin when clicking outside
  d3.select("body").on("click", function (event) {
    if (pinnedBar && !tooltip.node().contains(event.target)) {
      d3.select(pinnedBar)
        .attr("opacity", 1)
        .attr("stroke", "#fff")
        .attr("stroke-width", 0.5);
      hideTooltip(tooltip);
      pinnedBar = null;
    }
  });
};

window.determineData = function () {
  const discipline = d3
    .select("input[name='characteristics-discipline-filter']:checked")
    .node().value;

  console.log("Selected discipline:", discipline);

  let pyramidData;
  switch (discipline) {
    case "sport":
      pyramidData = DataManager.data.sport;
      break;
    case "trad":
      pyramidData = DataManager.data.trad;
      break;
    case "boulder":
      pyramidData = DataManager.data.boulder;
      break;
    default:
      console.error("Unknown discipline type");
      pyramidData = [];
  }

  console.log("Data for visualization:", {
    discipline,
    pyramidData,
    binnedCodeDict: DataManager.data.binnedCodes
  });

  return { pyramidData };
};

// Initialize visualization when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  if (!DataManager.init()) {
    return; // Stop if initialization fails
  }

  function updateVisualization() {
    console.log("Starting visualization update");
    const data = determineData();

    if (!data.pyramidData) {
      DataManager.showError('No data available for selected discipline');
      return;
    }

    window.characteristicsVizChart(
      "#performance-characteristics",
      data.pyramidData,
      DataManager.data.binnedCodes
    );
  }

  // Add event listeners using D3
  d3.selectAll("input[name='characteristics-discipline-filter']")
    .on("change", updateVisualization);

  d3.selectAll("input[name='characteristics-time-filter']")
    .on("change", updateVisualization);

  // Initial visualization
  updateVisualization();
});
