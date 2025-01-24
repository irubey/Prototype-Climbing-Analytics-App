// Make function globally available
function restDaysChart(targetElement, userTicksData) {
  // Clear existing chart
  d3.select(targetElement).select("svg").remove();

  // Get filters
  var discipline = d3
    .select("input[name='rest-days-discipline-filter']:checked")
    .node().value;
  var timeFrame = d3
    .select("input[name='rest-days-time-filter']:checked")
    .node().value;

  // Apply filters
  var filteredData = CommonFilters.filterByDiscipline(
    userTicksData,
    discipline
  );
  filteredData = CommonFilters.filterByTime(filteredData, timeFrame);

  // Format date for x-axis
  const formatMonth = d3.timeFormat("%b '%y");

  // Define seasonal colors (matching workCapacity.js)
  const seasonColors = {
    Spring: "#7CB9A8", // Sage Green
    Summer: "#F3B562", // Muted Gold
    Fall: "#DB784D", // Terracotta
    Winter: "#5B8BA0", // Dusty Blue
  };

  // Function to get color based on season
  const getSeasonColor = (seasonCategory) => {
    const season = seasonCategory.split(" ")[0].replace(",", "");
    return seasonColors[season] || "#4caf50";
  };

  // Pre-process data
  const monthsData = filteredData.reduce((acc, tick) => {
    const date = new Date(tick.tick_date);
    if (!isNaN(date)) {
      const monthYearKey = `${date.getMonth() + 1}-${date.getFullYear()}`;
      if (!acc[monthYearKey]) {
        acc[monthYearKey] = new Set();
        acc[monthYearKey].date = date;
        acc[monthYearKey].seasonCategory = tick.season_category;
      }
      acc[monthYearKey].add(date.toISOString().slice(0, 10));
    }
    return acc;
  }, {});

  // Get first and last dates from filtered data
  const dates = filteredData.map((d) => new Date(d.tick_date));
  const firstDate = d3.min(dates);
  const lastDate = d3.max(dates);

  // Go back to start of month to ensure we include partial first month
  const startDate = new Date(firstDate);
  startDate.setDate(1);
  const endDate = new Date(lastDate);
  endDate.setDate(1);

  // Generate all months between start and end date
  const currentDate = new Date(startDate);
  while (currentDate <= endDate) {
    const monthYearKey = `${
      currentDate.getMonth() + 1
    }-${currentDate.getFullYear()}`;
    if (!monthsData[monthYearKey]) {
      // If month doesn't exist in data, create empty entry
      monthsData[monthYearKey] = new Set();
      monthsData[monthYearKey].date = new Date(currentDate);

      // Determine season category based on month
      const month = currentDate.getMonth();
      const year = currentDate.getFullYear();
      const seasons = ["Winter", "Spring", "Summer", "Fall"];
      const seasonIndex = Math.floor(month / 3);
      const season = seasons[seasonIndex];

      // Special handling for Winter which spans years
      let seasonCategory;
      if (season === "Winter") {
        // Winter is Dec-Feb, so if we're in Dec, it's winter of current-next year
        const winterYear = month === 11 ? year : year - 1;
        seasonCategory = `Winter, ${winterYear}-${winterYear + 1}`;
      } else {
        seasonCategory = `${season}, ${year}`;
      }

      monthsData[monthYearKey].seasonCategory = seasonCategory;
    }
    currentDate.setMonth(currentDate.getMonth() + 1);
  }

  // Compute average climbing days
  const averageClimbingDays = Object.entries(monthsData).map(
    ([monthYear, daysSet]) => {
      const [month, year] = monthYear.split("-").map(Number);
      const totalDaysInMonth = new Date(year, month, 0).getDate();
      const weeksInMonth = totalDaysInMonth / 7;
      const averageClimbing = daysSet.size / weeksInMonth;

      return {
        monthYear,
        date: daysSet.date,
        seasonCategory: daysSet.seasonCategory,
        averageClimbing,
        averageRest: 7 - averageClimbing,
      };
    }
  );

  // Sort by date
  averageClimbingDays.sort((a, b) => a.date - b.date);

  // Calculate dimensions based on container width
  const container = d3.select(targetElement).node().getBoundingClientRect();
  const margin = { top: 20, right: 110, bottom: 60, left: 60 };
  const width = Math.min(container.width - margin.left - margin.right, 700);
  const height = width * 0.5;

  // Create SVG with responsive sizing
  const svg = d3
    .select(targetElement)
    .append("svg")
    .attr("width", "100%")
    .attr("height", height + margin.top + margin.bottom)
    .attr(
      "viewBox",
      `0 0 ${width + margin.left + margin.right} ${
        height + margin.top + margin.bottom
      }`
    )
    .attr("preserveAspectRatio", "xMidYMid meet")
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const color = d3
    .scaleOrdinal()
    .domain(["averageClimbing", "averageRest"])
    .range([(d) => getSeasonColor(d.data.seasonCategory), "#f5f5f5"]); // Dynamic color for climbing days

  // Scales
  const x = d3
    .scaleBand()
    .domain(averageClimbingDays.map((d) => d.monthYear))
    .range([0, width])
    .padding(0.1); // Reduced padding to make bars wider

  const y = d3.scaleLinear().domain([0, 7]).range([height, 0]);

  // Create stacked data
  const stackGen = d3
    .stack()
    .keys(["averageClimbing", "averageRest"])
    .order(d3.stackOrderNone)
    .offset(d3.stackOffsetNone);

  const stackedData = stackGen(averageClimbingDays);

  // Add bars with seasonal colors
  svg
    .selectAll("g.layer")
    .data(stackedData)
    .join("g")
    .attr("class", "layer")
    .attr("fill", (d) => {
      if (d.key === "averageClimbing") {
        return (d) => getSeasonColor(d.data.seasonCategory);
      }
      return "#f5f5f5"; // Rest/Gym color
    })
    .selectAll("rect")
    .data((d) => d)
    .join("rect")
    .attr("x", (d) => x(d.data.monthYear))
    .attr("y", (d) => y(d[1]))
    .attr("height", (d) => y(d[0]) - y(d[1]))
    .attr("width", x.bandwidth())
    .attr("fill", function (d) {
      const parentData = d3.select(this.parentNode).datum();
      if (parentData.key === "averageClimbing") {
        return getSeasonColor(d.data.seasonCategory);
      }
      return "#f5f5f5"; // Rest/Gym color
    })
    .style("transition", "opacity 0.2s") // Add transition for smooth opacity change
    .on("mouseover", function (event, d) {
      const parentData = d3.select(this.parentNode).datum();
      if (parentData.key === "averageClimbing") {
        // Highlight the bar
        d3.select(this).style("opacity", 0.8);

        // Show tooltip
        const value = d.data.averageClimbing;
        const tooltip = svg
          .append("text")
          .attr("class", "bar-tooltip")
          .attr("x", x(d.data.monthYear) + x.bandwidth() / 2)
          .attr("y", y(d[1]) - 5)
          .attr("text-anchor", "middle")
          .attr("font-size", "12px")
          .text(`${value.toFixed(1)} days/week`);
      }
    })
    .on("mouseout", function () {
      // Reset opacity
      d3.select(this).style("opacity", 1);
      // Remove tooltip
      svg.selectAll(".bar-tooltip").remove();
    });

  // Add grid lines AFTER bars so they appear on top
  const gridGroup = svg.append("g").attr("class", "grid-group");

  // Add major grid lines for each day
  gridGroup
    .selectAll(".grid-line")
    .data(d3.range(0, 8, 1))
    .enter()
    .append("line")
    .attr("class", "grid-line")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", (d) => y(d))
    .attr("y2", (d) => y(d))
    .attr("stroke", "#bdbdbd")
    .attr("stroke-width", 1)
    .style("stroke-dasharray", "2,2");

  // X Axis with filtered ticks and formatted dates
  const allMonths = averageClimbingDays.map((d) => d.monthYear);
  const numTicks = 12;
  const tickInterval = Math.ceil(allMonths.length / numTicks);
  const tickValues = allMonths.filter((_, i) => i % tickInterval === 0);

  svg
    .append("g")
    .attr("class", "x-axis")
    .attr("transform", `translate(0,${height})`)
    .call(
      d3
        .axisBottom(x)
        .tickValues(tickValues)
        .tickFormat((d) => {
          const entry = averageClimbingDays.find(
            (item) => item.monthYear === d
          );
          return formatMonth(entry.date);
        })
    )
    .selectAll("text")
    .style("text-anchor", "end")
    .attr("dx", "-.8em")
    .attr("dy", ".15em")
    .attr("transform", "rotate(-65)")
    .style("font-size", "11px");

  // Y Axis with numbers and label
  const yAxis = svg
    .append("g")
    .attr("class", "y-axis")
    .call(d3.axisLeft(y).ticks(7).tickFormat(d3.format("d")));

  yAxis.selectAll("text").style("font-size", "11px");

  // Add Y axis label
  yAxis
    .append("text")
    .attr("transform", "rotate(-90)")
    .attr("y", -60) // Adjust position
    .attr("x", -(height / 2))
    .attr("dy", "0.71em")
    .attr("text-anchor", "middle")
    .attr("fill", "black")
    .style("font-size", "12px")
    .text("Days Per Week");

  // Calculate average and total days
  const totalDays = d3.sum(
    averageClimbingDays,
    (d) =>
      d.averageClimbing *
      (new Date(d.date.getFullYear(), d.date.getMonth() + 1, 0).getDate() / 7)
  );
  const averageDaysPerWeek = d3.mean(
    averageClimbingDays,
    (d) => d.averageClimbing
  );

  // Legend and Stats
  const legendData = [
    { key: "Spring", label: "Spring" },
    { key: "Summer", label: "Summer" },
    { key: "Fall", label: "Fall" },
    { key: "Winter", label: "Winter" },
    { key: "rest", label: "Rest/Gym" },
  ];

  const legend = svg
    .append("g")
    .attr("transform", `translate(${width + 5},10)`);

  // Add legend items
  legendData.forEach((item, idx) => {
    const legendRow = legend
      .append("g")
      .attr("transform", `translate(0, ${idx * 20})`);

    legendRow
      .append("rect")
      .attr("width", 10)
      .attr("height", 10)
      .attr("fill", item.key === "rest" ? "#f5f5f5" : seasonColors[item.key]);

    legendRow
      .append("text")
      .attr("x", 15)
      .attr("y", 9)
      .style("font-size", "11px")
      .text(item.label);
  });

  // Add stats below legend
  const statsGroup = legend
    .append("g")
    .attr("transform", `translate(0, ${(legendData.length + 1) * 20})`);

  // Average days per week
  statsGroup
    .append("text")
    .attr("y", 0)
    .style("font-size", "11px")
    .style("font-weight", "600")
    .text(`Avg Days/Week: ${averageDaysPerWeek.toFixed(1)}`);

  // Total days
  statsGroup
    .append("text")
    .attr("y", 20)
    .style("font-size", "11px")
    .style("font-weight", "600")
    .text(`Total Days: ${Math.round(totalDays)}`);
}

// Add event listener for DOM ready
document.addEventListener("DOMContentLoaded", function () {
  // Any initialization code can go here
});
