function seasonalHeatmap(userTicksData, targetId) {
  // Set dimensions and margins
  const margin = { top: 50, right: 120, bottom: 50, left: 80 };

  // Get container width and calculate height for better aspect ratio
  const container = d3.select(targetId);
  const containerWidth = container.node().getBoundingClientRect().width;
  const width = containerWidth - margin.left - margin.right;
  const height = Math.min(width * 0.4, 400); // Better aspect ratio

  // Process data
  const dateParser = d3.timeParse("%Y-%m-%d");
  const processedData = userTicksData.reduce((acc, d) => {
    // Skip entries without a valid date
    const date = dateParser(d.tick_date);
    if (!date) return acc;

    const key = `${date.getFullYear()}-${date.getMonth() + 1}`;
    const dateKey = d.tick_date; // Use full date as key for uniqueness

    if (!acc[key]) {
      acc[key] = {
        year: date.getFullYear(),
        month: date.getMonth(),
        uniqueDates: new Set(),
        pitches: 0,
        disciplines: new Set(),
        locations: new Set(),
      };
    }

    // Add the date to track unique days
    acc[key].uniqueDates.add(dateKey);
    acc[key].pitches += d.pitches || 1;
    if (d.discipline) {
      acc[key].disciplines.add(d.discipline);
    }
    if (d.location) {
      acc[key].locations.add(d.location.trim());
    }
    return acc;
  }, {});

  // Convert the processed data to array format, calculating count from uniqueDates
  const data = Object.values(processedData).map((d) => ({
    ...d,
    count: d.uniqueDates.size, // Use size of uniqueDates Set for count
    uniqueDates: undefined, // Remove the Set from the final data
  }));

  const years = [...new Set(data.map((d) => d.year))].sort();
  const months = d3.range(12);

  // Clear any existing SVG
  d3.select(targetId).selectAll("svg").remove();

  // Create SVG with responsive sizing
  const svg = container
    .append("svg")
    .attr("width", "100%")
    .attr("height", height + margin.top + margin.bottom)
    .attr(
      "viewBox",
      `0 0 ${containerWidth} ${height + margin.top + margin.bottom}`
    )
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Create scales with increased padding
  const x = d3.scaleBand().domain(months).range([0, width]).padding(0.12);

  const y = d3.scaleBand().domain(years).range([0, height]).padding(0.12);

  // Updated color scale with warmer progression
  const color = d3
    .scaleSequential()
    .domain([0, d3.max(data, (d) => d.pitches)])
    .interpolator(d3.interpolateRgb("#fff5eb", "#7f0000"));

  // Add background for the chart area
  svg
    .append("rect")
    .attr("width", width)
    .attr("height", height)
    .attr("fill", "#fafafa")
    .attr("rx", 5);

  // Add grid lines with lighter color
  // Vertical grid lines
  svg
    .append("g")
    .selectAll("line")
    .data(months)
    .enter()
    .append("line")
    .attr("x1", (d) => x(d))
    .attr("x2", (d) => x(d))
    .attr("y1", 0)
    .attr("y2", height)
    .attr("stroke", "#f0f0f0")
    .attr("stroke-width", 1);

  // Horizontal grid lines
  svg
    .append("g")
    .selectAll("line")
    .data(years)
    .enter()
    .append("line")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", (d) => y(d))
    .attr("y2", (d) => y(d))
    .attr("stroke", "#f0f0f0")
    .attr("stroke-width", 1);

  // Add month labels at the bottom with improved styling
  svg
    .append("g")
    .selectAll("text")
    .data(months)
    .enter()
    .append("text")
    .text((d) => d3.timeFormat("%b")(new Date(2000, d)))
    .attr("x", (d) => x(d) + x.bandwidth() / 2)
    .attr("y", height + 25)
    .attr("text-anchor", "middle")
    .style("font-size", "12px")
    .style("font-weight", "500")
    .style("fill", "#666");

  // Add year labels with improved styling
  svg
    .append("g")
    .selectAll("text")
    .data(years)
    .enter()
    .append("text")
    .text((d) => d)
    .attr("x", -15)
    .attr("y", (d) => y(d) + y.bandwidth() / 2)
    .attr("text-anchor", "end")
    .attr("dominant-baseline", "middle")
    .style("font-size", "12px")
    .style("font-weight", "500")
    .style("fill", "#666");

  // Create cells with improved styling
  const cells = svg
    .selectAll(".cell")
    .data(data)
    .enter()
    .append("g")
    .attr("class", "cell");

  cells
    .append("rect")
    .attr("x", (d) => x(d.month))
    .attr("y", (d) => y(d.year))
    .attr("rx", 4)
    .attr("ry", 4)
    .attr("width", x.bandwidth())
    .attr("height", y.bandwidth())
    .attr("fill", (d) => color(d.pitches))
    .attr("stroke", "white")
    .attr("stroke-width", 2)
    .style("transition", "all 0.2s")
    .on("mouseover", function (event, d) {
      const tooltip = d3.select("#heatmap-tooltip");

      // Highlight the cell
      d3.select(this)
        .attr("stroke", "#000")
        .attr("stroke-width", 2)
        .style("filter", "brightness(1.1)");

      tooltip.transition().duration(200).style("opacity", 0.9);

      tooltip
        .html(
          `
        <div style="font-weight: bold; margin-bottom: 5px; font-size: 14px;">
          ${d3.timeFormat("%B %Y")(new Date(d.year, d.month))}
        </div>
        <div style="display: grid; grid-template-columns: auto 1fr; gap: 8px; font-size: 13px;">
          <span>📅 Days:</span> <span>${d.count} unique days</span>
          <span>🧗‍♂️ Pitches:</span> <span>${d.pitches} total pitches</span>
          <span style="align-self: start;">📍 Locations:</span> 
          <span style="max-height: 150px; overflow-y: auto;">
            ${(() => {
              const locationArray = Array.from(d.locations);
              const displayLocations = locationArray.slice(0, 8);
              const remaining = locationArray.length - 8;
              return (
                displayLocations.join("<br>") +
                (remaining > 0 ? `<br>...and ${remaining} more` : "")
              );
            })()}
          </span>
        </div>
      `
        )
        .style("left", event.pageX + 10 + "px")
        .style("top", event.pageY - 28 + "px");
    })
    .on("mouseout", function () {
      // Reset cell highlight
      d3.select(this)
        .attr("stroke", "white")
        .attr("stroke-width", 2)
        .style("filter", null);

      d3.select("#heatmap-tooltip")
        .transition()
        .duration(500)
        .style("opacity", 0);
    });

  // Improved legend with better positioning
  const legendWidth = 15;
  const legendHeight = 200;
  const legendTextPadding = 45; // Space for text

  const legendScale = d3
    .scaleLinear()
    .domain(color.domain())
    .range([legendHeight, 0]); // Flip range for vertical orientation

  const legendAxis = d3
    .axisRight(legendScale)
    .ticks(5)
    .tickFormat((d) => d + " pitches");

  // Position legend at the right side
  const legend = svg
    .append("g")
    .attr("class", "legend")
    .attr(
      "transform",
      `translate(${width + 40}, ${height / 2 - legendHeight / 2})`
    );

  // Add white background to legend for better visibility
  legend
    .append("rect")
    .attr("width", legendWidth + legendTextPadding + 10)
    .attr("height", legendHeight + 20)
    .attr("x", -5)
    .attr("y", -10)
    .attr("fill", "white")
    .attr("rx", 5)
    .attr("ry", 5)
    .attr("stroke", "#eee")
    .attr("stroke-width", 1);

  const defs = legend.append("defs");
  const linearGradient = defs
    .append("linearGradient")
    .attr("id", "linear-gradient")
    .attr("gradientUnits", "userSpaceOnUse")
    .attr("x1", 0)
    .attr("y1", legendHeight)
    .attr("x2", 0)
    .attr("y2", 0);

  linearGradient
    .selectAll("stop")
    .data(
      color.ticks(10).map((t, i, n) => ({
        offset: `${(100 * i) / n.length}%`,
        color: color(t),
      }))
    )
    .enter()
    .append("stop")
    .attr("offset", (d) => d.offset)
    .attr("stop-color", (d) => d.color);

  legend
    .append("rect")
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    .attr("rx", 3)
    .attr("ry", 3)
    .style("fill", "url(#linear-gradient)")
    .style("stroke", "#ccc")
    .style("stroke-width", 1);

  legend
    .append("g")
    .attr("transform", `translate(${legendWidth}, 0)`)
    .call(legendAxis)
    .selectAll("text")
    .style("font-size", "10px")
    .style("fill", "#666");
}
