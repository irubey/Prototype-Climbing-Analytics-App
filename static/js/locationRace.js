function locationRaceChart(userTicksData,targetId){
  const MARGIN = { top: 20, right: 20, bottom: 20, left: 150 };
  const topCount = 20;


  function location(userTicksData, targetId) {
    const [frames, uniqueLocations] = prepareData(userTicksData);

    const color = d3.scaleOrdinal().domain(uniqueLocations).range(d3.schemeCategory10);
    const { svg, x, y, containerWidth,effectiveHeight } = initializeChart(targetId, frames); 
    setupAxes(svg, x);
    ticker(svg, containerWidth,effectiveHeight);

    let frameIndex = 0;   // initialize here
    const keyframedFrames = keyframes(frames);   // initialize here

    renderBars(color, svg, x, y, frames, containerWidth, frameIndex, keyframedFrames);  // pass them down
  }

  function prepareData(userTicksData) {
    const aggregatedData = d3.rollups(
      userTicksData,
      v => d3.sum(v, leaf => leaf.pitches),
      d => new Date(d.tick_date),
      d => d.location.trim()
    );

    const uniqueLocations = Array.from(new Set(userTicksData.map(d => d.location.trim())));

    const dateLocationsMap = new Map();
    const locationTotalPitchesMap = new Map(); // New map to store cumulative total pitches for each location

    aggregatedData.forEach(([date, locations]) => {
      locations.forEach(([location, pitchCount]) => {
        // Calculate cumulative total pitches for each location
        const cumulativeTotal = locationTotalPitchesMap.get(location) || 0;
        locationTotalPitchesMap.set(location, cumulativeTotal + pitchCount);

        // Store cumulative total in the locationData array
        const locationData = Array.from(locationTotalPitchesMap, ([location, totalPitches]) => ({
          location,
          totalPitches,
        }));

        dateLocationsMap.set(date, locationData);
      });
    });

    const frames = Array.from(dateLocationsMap.entries()).map(([date, locationsData]) => ({
      date,
      locationsData,
    }));
    return [frames, uniqueLocations];
  }




  function initializeChart(targetId, frames) {
    // Get the reference to the target div element
    const container = document.querySelector(targetId);

    // Calculate the maximum totalPitches value
    const maxTotalPitches = d3.max(frames, d => d3.max(d.locationsData, locationData => locationData.totalPitches));

    // Calculate the effective height based on the topCount and other margins
    const effectiveHeight = topCount * 40;

    // Calculate the width based on the container's client width
    const containerWidth = container.clientWidth;

    // Define the x scale based on the maxTotalPitches and container width
    const x = d3.scaleLinear()
                .domain([0, maxTotalPitches])
                .range([MARGIN.left, containerWidth - MARGIN.right]);

    // Define the y scale as before
    const y = d3.scaleBand()
                .rangeRound([effectiveHeight - MARGIN.bottom, MARGIN.top])
                .padding(0.1);

    // Create the SVG element with the updated width
    const svg = d3.select(targetId).append("svg")
                  .attr("width", containerWidth - 20)
                  .attr("height", effectiveHeight)
                  .attr("viewBox", [0, 0, containerWidth, effectiveHeight])
                  .attr("preserveAspectRatio", "xMidYMid meet");

    return {svg, x, y, containerWidth,effectiveHeight};
  }


  function setupAxes(svg, x) {
    const xAxis = g => g.attr("transform", `translate(0, ${MARGIN.top})`)
                          .call(d3.axisTop(x).ticks(svg.attr("width") / 80)) // Adjust the ticks based on SVG width
                          .call(g => g.select(".domain").remove());

    svg.append("g").attr("class", "x-axis").call(xAxis);
  }

  function renderBars(color, svg, x, y, frames, containerWidth, frameIndex, keyframedFrames) {
    animateBars(color,svg, x, y, containerWidth, frameIndex, keyframedFrames);  // pass them down
  }

  function calculateBarWidth(x,d) {
    // Map totalPitches to the x-axis range
    const widthValue = x(d.totalPitches) - x(0);
    return isNaN(widthValue) ? 0 : widthValue;
  }


  function animateBars(color,svg, x, y, containerWidth, frameIndex, keyframedFrames) {
    if (frameIndex >= keyframedFrames.length) return;

    // Update the date label (Ticker) based on the current frame
    svg.select(".date-label")
    .text(d3.timeFormat("%Y-%m-%d")(keyframedFrames[frameIndex].date));

    const reversedData = [...keyframedFrames[frameIndex].locationsData].reverse();
    updateBars(color, reversedData, svg, x, y, containerWidth); // Pass the reversed data array
    
    frameIndex++;
    setTimeout(() => animateBars(color,svg, x, y, containerWidth, frameIndex, keyframedFrames), 200);  // Adjust delay as needed
  }



  function keyframes(frames) {
    return frames.map(({ date, locationsData }) => {
      const rankedDataArray = rank(locationsData, topCount); // Use the locationsData array directly
      return { date, locationsData: rankedDataArray };
    });
  }

  function rank(value, count) {
    if (!value) return [];
    const data = value
        .sort((a, b) => b.totalPitches - a.totalPitches)
        .slice(0, count);
    for (let i = 0; i < data.length; ++i) data[i].rank = i;
    return data;
  }

  function getMaxTextWidth(textArray) {
    const invisibleText = document.createElement("span");
    invisibleText.style.visibility = "hidden";
    invisibleText.style.position = "absolute";
    invisibleText.style.whiteSpace = "nowrap";
    invisibleText.style.font = "12px sans-serif"; // You can adjust the font size and style

    let maxWidth = 0;
    textArray.forEach(text => {
      invisibleText.textContent = text;
      document.body.appendChild(invisibleText);
      const width = invisibleText.getBoundingClientRect().width;
      maxWidth = Math.max(maxWidth, width);
      document.body.removeChild(invisibleText);
    });

    return maxWidth;
  }

  function updateBars(color,data,svg,x,y,containerWidth) {
    
    var maxTotalPitches = d3.max(data, d => d.totalPitches);
    
    y.domain(data.slice(0, topCount).map(d => d.location));
    x.domain([0, maxTotalPitches])

    // Update the x-axis
    svg.select(".x-axis").attr("transform", `translate(0, ${MARGIN.top})`).call(d3.axisTop(x));

    const bars = svg.selectAll(".bar")
      .data(data, d => d.location);

    // Remove bars that no longer have data
    bars.exit().remove();

    // Update existing bars
    bars.transition().duration(20)
      .attr("y", d => y(d.location))
      .attr("height", y.bandwidth())
      .attr("width", d => calculateBarWidth(x,d))
      .attr("fill", d => color(d.location))
      .attr("class", "bar")
      .attr("x", MARGIN.left)
      .attr("width", d => calculateBarWidth(x,d));

    // Add new bars
    bars.enter().append("rect")
      .attr("class", "bar")
      .attr("y", d => y(d.location))
      .attr("height", y.bandwidth())
      .attr("x", MARGIN.left)
      .attr("width", d => calculateBarWidth(x,d))
      .attr("fill", d => color(d.location));

    // Select all labels (location and pitch count)
    const labels = svg.selectAll(".label")
      .data(data.slice(0, topCount), d => d.location);

    // Update existing labels
    labels.transition().duration(20)
      .attr("x", d => {
        const labelX = calculateBarWidth(x,d) + MARGIN.left + 10;
        const maxTextWidth = getMaxTextWidth([`${d.location} - ${d.totalPitches} pitches`]);
        return Math.min(labelX, containerWidth - MARGIN.right - maxTextWidth - 30);
      })
      .attr("y", d => y(d.location) + y.bandwidth() / 2)
      .text(d => `${d.location} - ${d.totalPitches} pitches`)
      .attr("fill", "black");

    // Add new labels
    labels.enter().append("text")
      .attr("class", "label")
      .attr("x", d => {
        const labelX = calculateBarWidth(x,d) + MARGIN.left + 10;
        const maxTextWidth = getMaxTextWidth([`${d.location} - ${d.totalPitches} pitches`]);
        return Math.min(labelX, containerWidth - MARGIN.right - maxTextWidth - 30);
      })
      .attr("y", d => y(d.location) + y.bandwidth() / 2 - 16) // Adjust y position for location label
      .attr("dy", "0.35em")
      .text(d => d.location)
      .attr("fill", "black");

    // Remove labels for locations that are not in the topCount
    labels.exit().remove();
  }

  function ticker(svg, containerWidth,effectiveHeight){
    svg.append("text")
    .attr("class", "date-label")
    .attr("x", containerWidth * 0.8)
    .attr("y", effectiveHeight * 0.8)
    .attr("dy", "0.32em")
    .attr("text-anchor", "start")
    .attr("fill", "black");
  }

  location(userTicksData, targetId);

}
