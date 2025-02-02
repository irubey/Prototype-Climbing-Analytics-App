// Make function globally available
function workCapacityChart(targetId, userTicksData) {
  // Validate input data
  if (!userTicksData || !Array.isArray(userTicksData) || userTicksData.length === 0) {
    console.error('Invalid or empty user ticks data:', userTicksData);
    d3.select(targetId).html('<div class="alert alert-warning">No climbing data to visualize.</div>');
    return;
  }

  // Clear existing chart
  d3.select(targetId).select("svg").remove();

  // Get current filter values
  const discipline = d3
    .select("input[name='work-capacity-discipline-filter']:checked")
    .node()?.value || 'all';
  const timeFrame = d3
    .select("input[name='work-capacity-time-filter']:checked")
    .node()?.value || 'allTime';

  console.log('Filters:', { discipline, timeFrame });

  // Apply filters
  let filteredData = CommonFilters.filterByDiscipline(userTicksData, discipline);
  filteredData = CommonFilters.filterByTime(filteredData, timeFrame);

  console.log('Filtered Data:', {
    originalLength: userTicksData.length,
    filteredLength: filteredData.length,
    sample: filteredData[0]
  });

  // Data transformation and chart generation
  const transformedData = transformData(filteredData);
  const averageLengthMap = calculateAverageLength(transformedData);
  const updatedData = calculateDailyVertical(transformedData, averageLengthMap);
  const output = calculateTotalVertical(updatedData);

  // Generate new chart
  generateBarChart(output, targetId);
}

// Utilities
const parseDate = d3.timeParse("%Y-%m-%d");
const formatDate = d3.timeFormat("%Y-%m-%d");

// Data Calcs
function transformData(data) {
  return data.map((d) => ({
    date: parseDate(d.tick_date),
    seasonCategory: d.season_category || '',
    routeName: d.route_name,
    length: d.length === 0 ? null : d.length,
    pitches: d.pitches,
    length_category: d.length_category,
    discipline: d.discipline ? d.discipline.toLowerCase() : null
  }));
}

function calculateAverageLength(data) {
  const averageLengthMap = new Map();

  data.forEach((d) => {
    if (d.length !== null && !isNaN(d.length)) {
      const dateString = formatDate(d.date);
      if (!averageLengthMap.has(dateString)) {
        averageLengthMap.set(dateString, { sum: d.length, count: 1 });
      } else {
        const entry = averageLengthMap.get(dateString);
        entry.sum += d.length;
        entry.count++;
      }
    }
  });

  averageLengthMap.forEach((value, key) => {
    averageLengthMap.set(key, value.sum / value.count);
  });
  return averageLengthMap;
}

function calculateDailyVertical(data, averageLengthMap) {
  // Default lengths based on route type
  const defaultLengths = {
    sport: 80, // Average sport route 80ft
    trad: 100, // Average trad route 100ft
    boulder: 10, // Average boulder 10ft
    multipitch_base: 80, // Base length for multipitch pitches
  };

  return data
    .map((d) => {
      const dateString = formatDate(d.date);
      if (d.length === 0 || isNaN(d.length)) {
        // Try to use daily average first
        const dailyAvg = averageLengthMap.get(dateString);
        if (dailyAvg) {
          d.length = dailyAvg;
        } else {
          // If no daily average, use default based on discipline and type
          if (d.length_category === "multipitch") {
            // For multipitch without length, use base length * pitches
            d.length = defaultLengths.multipitch_base * d.pitches;
          } else if (d.discipline === "sport") {
            d.length = defaultLengths.sport;
          } else if (d.discipline === "trad") {
            d.length = defaultLengths.trad;
          } else if (d.discipline === "boulder") {
            d.length = defaultLengths.boulder;
          }
        }
      }
      return d;
    })
    .filter((d) => d.length !== null && d.length !== undefined);
}

function calculateTotalVertical(data) {
  const verticalMap = new Map();

  // First calculate the vertical feet for each climb
  const processedData = data.map((d) => {
    let vertical;
    if (d.length_category === "multipitch") {
      vertical = d.length; // Use total route length for multipitch
    } else {
      vertical = d.length * d.pitches; // For single pitch, multiply by number of pitches
    }
    return {
      ...d,
      vertical: vertical,
    };
  });

  // Get date range
  const firstDate = d3.min(data, (d) => d.date);
  const lastDate = d3.max(data, (d) => d.date);

  // Generate all seasons between first and last date
  const currentDate = new Date(firstDate);
  const seasons = ["Winter", "Spring", "Summer", "Fall"];

  // Go back to start of season to ensure we include partial first season
  currentDate.setMonth(Math.floor(currentDate.getMonth() / 3) * 3);

  while (currentDate <= lastDate) {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const seasonIndex = Math.floor(month / 3);
    const season = seasons[seasonIndex];

    // Special handling for Winter which spans years
    let seasonKey;
    if (season === "Winter") {
      const winterYear = month === 11 ? year : year - 1;
      seasonKey = `Winter, ${winterYear}-${winterYear + 1}`;
    } else {
      seasonKey = `${season}, ${year}`;
    }

    // Initialize season if not exists
    if (!verticalMap.has(seasonKey)) {
      verticalMap.set(seasonKey, {
        totalVertical: 0,
        climbingDays: new Set(), // Track unique climbing days
        seasonCategory: seasonKey,
      });
    }

    // Move to next season
    currentDate.setMonth(currentDate.getMonth() + 3);
  }

  // Aggregate data by season
  processedData.forEach((d) => {
    const mapKey = d.seasonCategory;
    if (verticalMap.has(mapKey)) {
      const current = verticalMap.get(mapKey);
      current.totalVertical += d.vertical;
      current.climbingDays.add(d.date.toISOString().slice(0, 10));
    }
  });

  // Calculate daily averages and create output
  const output = [];
  verticalMap.forEach((value, key) => {
    // Parse date for sorting, handling winter season format
    let sortDate;
    if (key.startsWith("Winter")) {
      const winterYear = parseInt(key.split(" ")[1].split("-")[0]);
      sortDate = new Date(winterYear, 11, 1); // December of first year
    } else {
      sortDate = parseDate(key.split(",")[1].trim() + "-01-01");
    }

    // Calculate average vertical feet per climbing day
    const daysInSeason = value.climbingDays.size;
    const averageVertical =
      daysInSeason > 0 ? value.totalVertical / daysInSeason : 0;

    output.push({
      date: sortDate,
      totalVertical: averageVertical, // This is now average per climbing day
      seasonCategory: key,
    });
  });

  // Sort by date
  return output.sort((a, b) => a.date - b.date);
}

//Chart setup and generation
function setupChart(targetId) {
  // Calculate dimensions based on container width
  const container = d3.select(targetId).node().getBoundingClientRect();
  // Increase bottom margin for x-axis labels and left margin for y-axis
  const margin = { top: 20, right: 110, bottom: 100, left: 80 };
  // Limit max width and make it slightly smaller
  const width = Math.min(container.width - margin.left - margin.right, 700);
  // Use same height ratio as totalVert
  const height = width * 0.5;

  const svg = d3
    .select(targetId)
    .append("svg")
    .attr("width", "100%")
    .attr("height", height + margin.top + margin.bottom)
    .attr(
      "viewBox",
      `0 0 ${width + margin.left + margin.right} ${
        height + margin.top + margin.bottom
      }`
    )
    .attr("preserveAspectRatio", "xMidYMid meet");

  const g = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleBand().rangeRound([0, width]).paddingInner(0.05).align(0.1);
  const y = d3.scaleLinear().rangeRound([height, 0]);
  
  return { svg, g, x, y, width, height, margin };
}

function generateBarChart(data, targetId) {
  // Compute average for each seasonCategory
  const averageData = Array.from(
    d3.rollup(
      data,
      (group) => ({
        seasonCategory: group[0].seasonCategory,
        averageVertical: d3.mean(group, (d) => d.totalVertical) || 0,
        averagePitches: d3.mean(group, (d) => d.totalPitches) || 0,
      }),
      (d) => d.seasonCategory
    ),
    ([_, entry]) => entry
  );

  const { svg, g, x, y, width, height, margin } = setupChart(targetId);

  // Define base seasonal colors
  const seasonColors = {
    Spring: "#7CB9A8", // Sage Green
    Summer: "#F3B562", // Muted Gold
    Fall: "#DB784D", // Terracotta
    Winter: "#5B8BA0", // Dusty Blue
  };

  // Function to get color based on season
  const getSeasonColor = (seasonCategory) => {
    const season = seasonCategory
      ? seasonCategory.split(" ")[0].replace(",", "")
      : "";
    return seasonColors[season] || "#4caf50";
  };

  x.domain(averageData.map((d) => d.seasonCategory));
  y.domain([0, d3.max(averageData, (d) => d.averageVertical)]);

  // Calculate the overall averages
  const overallAverage = d3.mean(averageData, (d) => d.averageVertical);
  const overallPitches = d3.mean(averageData, (d) => d.averagePitches);

  // Add bars with seasonal colors
  g.selectAll(".bar")
    .data(averageData)
    .enter()
    .append("rect")
    .attr("class", "bar")
    .attr("x", (d) => x(d.seasonCategory))
    .attr("y", (d) => y(d.averageVertical))
    .attr("width", x.bandwidth())
    .attr("height", (d) => height - y(d.averageVertical))
    .style("fill", (d) => getSeasonColor(d.seasonCategory))
    .style("stroke", "none")
    .style("transition", "opacity 0.2s")
    .on("mouseover", function (event, d) {
      d3.select(this).style("opacity", 0.8);

      // Show tooltip with vertical feet only
      const season = d.seasonCategory.split(" ")[0].replace(",", "");
      const tooltip = g
        .append("text")
        .attr("class", "bar-tooltip")
        .attr("x", x(d.seasonCategory) + x.bandwidth() / 2)
        .attr("y", y(d.averageVertical) - 5)
        .attr("text-anchor", "middle")
        .attr("font-size", "12px")
        .text(`${season}: ${Math.round(d.averageVertical)} ft/day`);
    })
    .on("mouseout", function () {
      d3.select(this).style("opacity", 1);
      g.selectAll(".bar-tooltip").remove();
    });

  // Add average line
  g.append("line")
    .attr("class", "average-line")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", y(overallAverage))
    .attr("y2", y(overallAverage))
    .style("stroke", "#2d3250")
    .style("stroke-dasharray", "4,4")
    .style("stroke-width", 1.5);

  // Add average label with vertical feet only
  g.append("text")
    .attr("class", "average-label")
    .attr("x", width + 5)
    .attr("y", y(overallAverage))
    .attr("dy", "0.32em")
    .attr("font-size", "11px")
    .attr("font-weight", "600")
    .attr("fill", "#2d3250")
    .text(`Average: ${Math.round(overallAverage)} ft/day`);

  // Add seasonal legend
  const legendData = [
    { key: "Spring", label: "Spring" },
    { key: "Summer", label: "Summer" },
    { key: "Fall", label: "Fall" },
    { key: "Winter", label: "Winter" },
  ];

  const legend = g.append("g").attr("transform", `translate(${width + 5}, 10)`);

  legendData.forEach((item, idx) => {
    const legendRow = legend
      .append("g")
      .attr("transform", `translate(0, ${idx * 20})`);

    legendRow
      .append("rect")
      .attr("width", 10)
      .attr("height", 10)
      .attr("fill", seasonColors[item.key]);

    legendRow
      .append("text")
      .attr("x", 15)
      .attr("y", 9)
      .style("font-size", "11px")
      .text(item.label);
  });

  // Update axis rendering
  // X Axis
  g.append("g")
    .attr("transform", `translate(0, ${height})`)
    .call(d3.axisBottom(x).tickSizeOuter(0))
    .selectAll("text")
    .style("text-anchor", "end")
    .attr("dx", "-.8em")
    .attr("dy", ".15em")
    .attr("transform", "rotate(-65)")
    .style("font-size", "11px"); // Make text slightly smaller

  // Y Axis with formatted ticks
  const yAxis = g.append("g").call(
    d3
      .axisLeft(y)
      .ticks(6) // Limit number of ticks
      .tickFormat((d) => {
        if (d >= 1000) {
          return d / 1000 + "k";
        }
        return d;
      })
  );

  // Y axis label
  yAxis
    .append("text")
    .attr("transform", "rotate(-90)")
    .attr("y", -60) // Adjust position
    .attr("x", -(height / 2))
    .attr("dy", "0.71em")
    .attr("text-anchor", "middle")
    .attr("fill", "black")
    .style("font-size", "12px")
    .text("Average Daily Vertical Feet");
}

// Add event listener for DOM ready
document.addEventListener("DOMContentLoaded", function () {
  // Any initialization code can go here
});
