const SVG_DEFAULTS = {
  width: 600,
  height: 400,
  margin: { top: 20, right: 30, bottom: 150, left: 60 },
};

function daysOutsideChart(targetId, userTicksData, customSVG = SVG_DEFAULTS) {
  // Clear any existing SVG
  d3.select(targetId).select("svg").remove();

  // Get current time filter
  const timeFilter =
    d3.select("input[name='days-outside-time-filter']:checked").node()?.value ||
    "allTime";

  // Apply filters
  const filteredData =
    timeFilter === "allTime"
      ? userTicksData
      : userTicksData.filter((d) => {
          const date = new Date(d.tick_date);
          const yearAgo = new Date();
          yearAgo.setFullYear(yearAgo.getFullYear() - 1);
          return date >= yearAgo;
        });

  function prepareData(userTicksData) {
    const uniqueDates = new Set();

    return userTicksData.reduce((acc, curr) => {
      const date = new Date(curr.tick_date);
      const seasonCategory = curr.season_category;
      const discipline = curr.discipline;

      if (
        !isNaN(date) &&
        seasonCategory &&
        seasonCategory.trim() &&
        discipline &&
        discipline.trim()
      ) {
        const dateString = date.toISOString().slice(0, 10);

        if (!uniqueDates.has(dateString)) {
          uniqueDates.add(dateString);
          acc.push({
            date: date,
            seasonCategory: seasonCategory,
            discipline: discipline,
          });
        }
      }
      return acc;
    }, []);
  }

  function groupDataByCategory(data) {
    return data.reduce((groups, item) => {
      const seasonKey = item.seasonCategory;
      if (!groups[seasonKey]) {
        groups[seasonKey] = {};
      }
      groups[seasonKey][item.discipline] =
        (groups[seasonKey][item.discipline] || 0) + 1;
      return groups;
    }, {});
  }

  function extractUniqueDisciplines(userTicksData) {
    return Object.keys(
      userTicksData.reduce((unique, item) => {
        if (item.discipline) unique[item.discipline] = true;
        return unique;
      }, {})
    );
  }

  function createHistogramData(groupedData) {
    return Object.entries(groupedData).map(([seasonCategory, disciplines]) => ({
      seasonCategory,
      ...disciplines,
    }));
  }

  function createBarChartDaysOutside(
    svg,
    histogramData,
    sortedDisciplines,
    x,
    y,
    color
  ) {
    const stack = d3
      .stack()
      .keys(sortedDisciplines)
      .order(d3.stackOrderNone)
      .offset(d3.stackOffsetNone);
    const stackedData = stack(histogramData);

    svg
      .selectAll(".seasonCategory")
      .data(stackedData)
      .enter()
      .append("g")
      .attr("class", "seasonCategory")
      .attr("fill", (d) => color(d.key))
      .selectAll("rect")
      .data((d) => d)
      .enter()
      .append("rect")
      .attr("x", (d) => x(d.data.seasonCategory))
      .attr("y", (d) => y(d[1]))
      .attr("height", (d) => y(d[0]) - y(d[1]))
      .attr("width", x.bandwidth());
  }

  function createAxes(svg, x, y, height) {
    svg
      .append("g")
      .attr("class", "x-axis")
      .attr("transform", `translate(0, ${height})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .style("text-anchor", "end")
      .attr("dx", "-.8em")
      .attr("dy", ".15em")
      .attr("transform", "rotate(-65)");

    svg.append("g").attr("class", "y-axis").call(d3.axisLeft(y));
  }

  function createLegend(svg, sortedDisciplines, color, width) {
    const legend = svg
      .selectAll(".legend")
      .data(sortedDisciplines)
      .enter()
      .append("g")
      .attr("class", "legend")
      .attr("transform", (d, i) => `translate(0, ${i * 20 + 50})`);

    legend
      .append("rect")
      .attr("x", width - 18)
      .attr("width", 18)
      .attr("height", 18)
      .attr("fill", color);

    legend
      .append("text")
      .attr("x", width - 24)
      .attr("y", 9)
      .attr("dy", ".35em")
      .style("text-anchor", "end")
      .text((d) => d);
  }

  // Initialize with filtered data
  const data = prepareData(filteredData);
  const groupedData = groupDataByCategory(data);
  const histogramData = createHistogramData(groupedData);
  const disciplines = extractUniqueDisciplines(filteredData);

  histogramData.forEach((d) => {
    disciplines.forEach((discipline) => {
      if (!d[discipline]) d[discipline] = 0;
    });
  });

  const disciplineTotals = disciplines.map((discipline) =>
    histogramData.reduce(
      (total, dataPoint) => total + (dataPoint[discipline] || 0),
      0
    )
  );

  const sortedDisciplines = disciplines
    .slice()
    .sort(
      (a, b) =>
        disciplineTotals[disciplines.indexOf(b)] -
        disciplineTotals[disciplines.indexOf(a)]
    );

  const { width, height, margin } = customSVG;

  const x = d3
    .scaleBand()
    .domain(histogramData.map((d) => d.seasonCategory))
    .range([0, width - margin.left - margin.right])
    .padding(0.2);

  const y = d3
    .scaleLinear()
    .domain([
      0,
      d3.max(histogramData, (d) =>
        d3.sum(sortedDisciplines.map((discipline) => d[discipline] || 0))
      ),
    ])
    .nice()
    .range([height - margin.top - margin.bottom, 0]);

  const color = d3
    .scaleOrdinal()
    .domain(sortedDisciplines)
    .range(d3.schemeSet2);

  const svg = d3
    .select(targetId)
    .append("svg")
    .attr("width", width)
    .attr("height", height)
    .append("g")
    .attr("transform", `translate(${margin.left}, ${margin.top})`);

  createBarChartDaysOutside(svg, histogramData, sortedDisciplines, x, y, color);
  createAxes(svg, x, y, height - margin.top - margin.bottom);
  createLegend(
    svg,
    sortedDisciplines,
    color,
    width - margin.left - margin.right
  );
}

// Add event listener for radio buttons
d3.selectAll("input[name='days-outside-time-filter']").on(
  "change",
  function () {
    daysOutsideChart("#days-outside", userTicksData, SVG_DEFAULTS);
  }
);
