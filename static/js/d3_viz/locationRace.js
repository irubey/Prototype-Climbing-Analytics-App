function locationRaceChart(userTicksData, targetId) {
  const MARGIN = { top: 20, right: 110, bottom: 60, left: 60 };
  const topCount = 20;
  const TOTAL_DURATION = 30000; // 30 seconds in milliseconds
  let isPlaying = true;
  let currentSpeed = 1;

  function location(userTicksData, targetId) {
    const [frames, uniqueLocations] = prepareData(userTicksData);
    const color = d3
      .scaleOrdinal()
      .domain(uniqueLocations)
      .range(d3.schemeCategory10);
    const { svg, x, y, containerWidth, effectiveHeight } = initializeChart(
      targetId,
      frames
    );
    setupAxes(svg, x);
    ticker(svg, containerWidth, effectiveHeight, y);

    const keyframedFrames = keyframes(frames);
    startAnimation(
      color,
      svg,
      x,
      y,
      containerWidth,
      effectiveHeight,
      keyframedFrames
    );
  }

  function prepareData(userTicksData) {
    // Pre-process dates once
    const dateParser = d3.timeParse("%Y-%m-%d");
    const processedData = userTicksData.map((d) => ({
      ...d,
      date: dateParser(d.tick_date),
      location: d.location.trim(),
    }));

    // Use more efficient d3.group instead of rollups for initial grouping
    const locationsByDate = d3.group(
      processedData,
      (d) => d.date,
      (d) => d.location
    );
    const uniqueLocations = new Set(processedData.map((d) => d.location));

    // Pre-calculate cumulative totals
    const dateLocationsMap = new Map();
    const locationTotalPitchesMap = new Map();

    // Convert to array once and sort
    Array.from(locationsByDate.entries())
      .sort(([a], [b]) => d3.ascending(a, b))
      .forEach(([date, locations]) => {
        // Sum pitches for each location on this date
        locations.forEach((locationData, location) => {
          const pitchCount = d3.sum(locationData, (d) => d.pitches);
          const prevTotal = locationTotalPitchesMap.get(location) || 0;
          locationTotalPitchesMap.set(location, prevTotal + pitchCount);
        });

        // Create frame data
        const locationData = Array.from(
          locationTotalPitchesMap,
          ([location, totalPitches]) => ({
            location,
            totalPitches,
          })
        );

        dateLocationsMap.set(date, locationData);
      });

    const frames = Array.from(dateLocationsMap.entries()).map(
      ([date, locationsData]) => ({
        date,
        locationsData: locationsData
          .sort((a, b) => b.totalPitches - a.totalPitches)
          .slice(0, topCount),
      })
    );

    return [frames, uniqueLocations];
  }

  function initializeChart(targetId, frames) {
    // Cache DOM element and get container width
    const container = d3.select(targetId);
    const containerWidth = container.node().getBoundingClientRect().width;
    const width = containerWidth - MARGIN.left - MARGIN.right;
    const effectiveHeight = width * 0.4;

    // Pre-calculate dimensions
    const availableHeight = effectiveHeight - MARGIN.top - MARGIN.bottom;
    const optimalBarHeight = Math.max(20, (availableHeight / topCount) * 0.8);
    const totalHeight = optimalBarHeight * topCount * 1.15; // 0.15 padding

    // Pre-calculate max value for x domain
    const maxTotalPitches = d3.max(frames, (d) =>
      d3.max(d.locationsData, (locationData) => locationData.totalPitches)
    );

    const x = d3
      .scaleLinear()
      .domain([0, maxTotalPitches])
      .range([MARGIN.left, containerWidth - MARGIN.right]);

    const y = d3
      .scaleBand()
      .range([MARGIN.top, MARGIN.top + totalHeight])
      .padding(0.15)
      .domain(
        Array(topCount)
          .fill(0)
          .map((_, i) => i)
      );

    // Create SVG with all attributes at once
    const svg = d3
      .select(targetId)
      .append("svg")
      .attr("width", "100%")
      .attr(
        "height",
        Math.max(effectiveHeight, totalHeight) + MARGIN.top + MARGIN.bottom
      )
      .attr(
        "viewBox",
        `0 0 ${containerWidth} ${
          Math.max(effectiveHeight, totalHeight) + MARGIN.top + MARGIN.bottom
        }`
      )
      .attr("preserveAspectRatio", "xMidYMid meet");

    return {
      svg,
      x,
      y,
      containerWidth,
      effectiveHeight: Math.max(effectiveHeight, totalHeight),
    };
  }

  function setupAxes(svg, x) {
    const xAxis = (g) =>
      g
        .attr("transform", `translate(0, ${MARGIN.top})`)
        .call(d3.axisTop(x).ticks(svg.attr("width") / 80))
        .call((g) => g.select(".domain").remove());

    svg.append("g").attr("class", "x-axis").call(xAxis);
  }

  function createControls(
    svg,
    containerWidth,
    effectiveHeight,
    keyframedFrames,
    animate,
    updateVisualization,
    handleRestart
  ) {
    const controlsG = svg
      .append("g")
      .attr("class", "controls")
      .attr(
        "transform",
        `translate(${MARGIN.left}, ${effectiveHeight + MARGIN.bottom - 30})`
      );

    // Play/Pause button
    const playButton = controlsG
      .append("g")
      .attr("class", "play-button")
      .attr("transform", "translate(0, 0)")
      .style("cursor", "pointer")
      .on("click", togglePlay)
      .on("mouseover", function () {
        d3.select(this).select("circle").attr("fill", "#f0f0f0");
      })
      .on("mouseout", function () {
        d3.select(this).select("circle").attr("fill", "white");
      });

    playButton
      .append("circle")
      .attr("r", 15)
      .attr("fill", "white")
      .attr("stroke", "#666");

    // Create play icon (triangle)
    const playPath = playButton.append("path").attr("fill", "#666");

    // Create pause icon (two rectangles)
    const pauseG = playButton.append("g").style("opacity", 0); // Initially hidden

    pauseG
      .append("rect")
      .attr("x", -4)
      .attr("y", -5)
      .attr("width", 3)
      .attr("height", 10)
      .attr("fill", "#666");

    pauseG
      .append("rect")
      .attr("x", 1)
      .attr("y", -5)
      .attr("width", 3)
      .attr("height", 10)
      .attr("fill", "#666");

    // Initial state
    updatePlayPauseButton(isPlaying);

    function updatePlayPauseButton(playing) {
      if (playing) {
        playPath.style("opacity", 0);
        pauseG.style("opacity", 1);
      } else {
        playPath.style("opacity", 1).attr("d", "M-4,-6 L-4,6 L6,0 Z");
        pauseG.style("opacity", 0);
      }
    }

    function togglePlay() {
      isPlaying = !isPlaying;
      updatePlayPauseButton(isPlaying);
      if (isPlaying) animate();
    }

    // Restart button
    const restartButton = controlsG
      .append("g")
      .attr("class", "restart-button")
      .attr("transform", "translate(40, 0)")
      .style("cursor", "pointer")
      .on("click", handleRestart)
      .on("mouseover", function () {
        d3.select(this).select("circle").attr("fill", "#f0f0f0");
      })
      .on("mouseout", function () {
        d3.select(this).select("circle").attr("fill", "white");
      });

    restartButton
      .append("circle")
      .attr("r", 15)
      .attr("fill", "white")
      .attr("stroke", "#666");

    // Standard replay icon (circular arrow)
    restartButton
      .append("path")
      .attr("fill", "#666")
      .attr(
        "d",
        "M 0,-7 A 7,7 0 1,1 -7,0 L-5,0 A 5,5 0 1,0 0,-5 L 0,-7 L 3,-4 L -3,-4 L 0,-7 Z"
      );

    // Speed control
    const speedControl = controlsG
      .append("g")
      .attr("class", "speed-control")
      .attr("transform", "translate(90, 0)");

    const speeds = [1, 2, 4];
    speeds.forEach((speed, i) => {
      speedControl
        .append("rect")
        .attr("x", i * 45)
        .attr("y", -10)
        .attr("width", 35)
        .attr("height", 20)
        .attr("rx", 5)
        .attr("fill", speed === currentSpeed ? "#666" : "#eee")
        .attr("class", "speed-button")
        .style("cursor", "pointer")
        .on("click", () => changeSpeed(speed));

      speedControl
        .append("text")
        .attr("x", i * 45 + 12)
        .attr("y", 5)
        .attr("text-anchor", "middle")
        .attr("fill", speed === currentSpeed ? "white" : "black")
        .text(speed + "x")
        .style("cursor", "pointer")
        .on("click", () => changeSpeed(speed));
    });

    // Progress indicator
    const timelineWidth = containerWidth - 280;
    const timeline = controlsG
      .append("g")
      .attr("class", "timeline")
      .attr("transform", `translate(${240}, 0)`);

    // Background line
    timeline
      .append("line")
      .attr("x1", 0)
      .attr("x2", timelineWidth)
      .attr("y1", 0)
      .attr("y2", 0)
      .attr("stroke", "#ddd")
      .attr("stroke-width", 2);

    // Add year marks
    const years = new Set(
      keyframedFrames.map((frame) => new Date(frame.date).getFullYear())
    );
    const yearArray = Array.from(years).sort();
    const minYearSpacing = 50; // Minimum pixels between year labels

    let lastLabelX = -Infinity;
    yearArray.forEach((year) => {
      // Find first frame of each year
      const yearFirstFrame = keyframedFrames.findIndex(
        (frame) => new Date(frame.date).getFullYear() === year
      );

      if (yearFirstFrame !== -1) {
        const x =
          (yearFirstFrame / (keyframedFrames.length - 1)) * timelineWidth;

        // Only add label if it won't overlap with previous label
        if (x - lastLabelX >= minYearSpacing) {
          // Add year mark line
          timeline
            .append("line")
            .attr("x1", x)
            .attr("x2", x)
            .attr("y1", -5)
            .attr("y2", 5)
            .attr("stroke", "#666")
            .attr("stroke-width", 1);

          // Add year label
          timeline
            .append("text")
            .attr("x", x)
            .attr("y", 15)
            .attr("text-anchor", "middle")
            .attr("font-size", "10px")
            .attr("fill", "#666")
            .text(year);

          lastLabelX = x;
        } else {
          // Still add the mark line even if we skip the label
          timeline
            .append("line")
            .attr("x1", x)
            .attr("x2", x)
            .attr("y1", -5)
            .attr("y2", 5)
            .attr("stroke", "#666")
            .attr("stroke-width", 1)
            .style("opacity", 0.5); // Lighter mark for unlabeled years
        }
      }
    });

    // Progress indicator circle
    const progressIndicator = timeline
      .append("circle")
      .attr("r", 6)
      .attr("cx", 0)
      .attr("cy", 0)
      .attr("fill", "#666")
      .attr("stroke", "none");

    function updateProgress(frameIndex) {
      const x = (frameIndex / (keyframedFrames.length - 1)) * timelineWidth;
      progressIndicator.attr("cx", x);
    }

    function changeSpeed(speed) {
      currentSpeed = speed;
      speedControl
        .selectAll(".speed-button")
        .attr("fill", (d) => (d === speed ? "#666" : "#eee"));
      speedControl.selectAll("text").attr("fill", function () {
        const buttonSpeed = parseFloat(this.textContent);
        return buttonSpeed === speed ? "white" : "black";
      });
    }

    return { updateProgress, updatePlayPauseButton };
  }

  function startAnimation(
    color,
    svg,
    x,
    y,
    containerWidth,
    effectiveHeight,
    keyframedFrames
  ) {
    let frameIndex = 0;
    let animationTimer;
    let controls;

    const frameDuration = TOTAL_DURATION / keyframedFrames.length;

    function updateVisualization(index) {
      const transition = svg
        .transition()
        .duration(frameDuration / currentSpeed)
        .ease(d3.easeLinear);

      svg
        .select(".date-label")
        .transition(transition)
        .text(d3.timeFormat("%Y-%m-%d")(keyframedFrames[index].date));

      const reversedData = [...keyframedFrames[index].locationsData].reverse();
      return updateBars(
        color,
        reversedData,
        svg,
        x,
        y,
        containerWidth,
        transition
      );
    }

    function animate() {
      if (!isPlaying || frameIndex >= keyframedFrames.length) {
        if (frameIndex >= keyframedFrames.length) {
          frameIndex = 0;
          controls.updateProgress(frameIndex);
        }
        return;
      }

      updateVisualization(frameIndex).then(() => {
        controls.updateProgress(frameIndex);
        frameIndex++;
        animationTimer = setTimeout(animate, frameDuration / currentSpeed);
      });
    }

    function handleRestart() {
      // Clear any existing animation
      if (animationTimer) {
        clearTimeout(animationTimer);
      }

      // Reset state
      frameIndex = 0;
      isPlaying = true;

      // Update UI
      controls.updatePlayPauseButton(true);
      controls.updateProgress(0);

      // Start from beginning
      updateVisualization(0).then(() => {
        animate();
      });
    }

    // Create controls after defining handleRestart
    controls = createControls(
      svg,
      containerWidth,
      effectiveHeight,
      keyframedFrames,
      animate,
      updateVisualization,
      handleRestart.bind(null)
    );

    animate();

    return { animate, updateVisualization };
  }

  function updateBars(color, data, svg, x, y, containerWidth, transition) {
    // Pre-sort data once
    const sortedData = data
      .slice(0, topCount)
      .sort((a, b) => b.totalPitches - a.totalPitches);

    const textPadding = 10;
    const valuePadding = 15;

    // Update scales
    y.domain(sortedData.map((d) => d.location));
    x.domain([0, d3.max(sortedData, (d) => d.totalPitches)]);

    // Update axis with transition
    svg.select(".x-axis").transition(transition).call(d3.axisTop(x));

    // Update bars with new data
    const bars = svg.selectAll(".bar").data(sortedData, (d) => d.location);

    // Handle exit
    bars.exit().transition(transition).attr("width", 0).remove();

    // Handle update
    bars
      .transition(transition)
      .attr("y", (d) => y(d.location))
      .attr("height", y.bandwidth())
      .attr("width", (d) => x(d.totalPitches) - x(0))
      .attr("fill", (d) => color(d.location))
      .attr("fill-opacity", 0.6)
      .attr("x", MARGIN.left);

    // Handle enter
    bars
      .enter()
      .append("rect")
      .attr("class", "bar")
      .attr("y", (d) => y(d.location))
      .attr("height", y.bandwidth())
      .attr("x", MARGIN.left)
      .attr("width", 0)
      .attr("fill", (d) => color(d.location))
      .attr("fill-opacity", 0.6)
      .transition(transition)
      .attr("width", (d) => x(d.totalPitches) - x(0));

    // Cache label measurements
    const labelCache = new Map();
    sortedData.forEach((d) => {
      const text = d.location;
      if (!labelCache.has(text)) {
        labelCache.set(text, getMaxTextWidth([text]));
      }
    });

    // Update labels
    const labels = svg.selectAll(".label").data(sortedData, (d) => d.location);

    // Handle label exit
    labels.exit().transition(transition).attr("opacity", 0).remove();

    // Location labels
    const labelGroups = labels
      .enter()
      .append("g")
      .attr("class", "label")
      .merge(labels)
      .attr(
        "transform",
        (d) => `translate(${MARGIN.left}, ${y(d.location) + y.bandwidth() / 2})`
      );

    // Value labels at end of bars
    labelGroups
      .selectAll(".value-text")
      .data((d) => [d])
      .join("text")
      .attr("class", "value-text")
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .style("font", "bold 12px var(--sans-serif)")
      .attr("fill", "black")
      .transition(transition)
      .attr("x", function (d) {
        const barWidth = x(d.totalPitches) - x(0);
        const valueWidth = this.getComputedTextLength();
        // Ensure value is always inside bar and has minimum padding
        return Math.max(valueWidth + textPadding, barWidth - valuePadding);
      })
      .text((d) => d.totalPitches);

    // Location text with dynamic positioning
    labelGroups
      .selectAll(".location-text")
      .data((d) => [d])
      .join("text")
      .attr("class", "location-text")
      .attr("dy", "0.35em")
      .attr("fill", "black")
      .style("font", "bold 12px var(--sans-serif)")
      .text((d) => d.location)
      .each(function (d) {
        const barWidth = x(d.totalPitches) - x(0);
        const textWidth = this.getComputedTextLength();
        const valueWidth = String(d.totalPitches).length * 10;

        // If bar is wide enough for both text and value
        if (barWidth > textWidth + textPadding * 3 + valueWidth) {
          d3.select(this).attr("x", textPadding).attr("fill", "black");
        } else {
          // Place after bar
          d3.select(this)
            .attr("x", barWidth + textPadding)
            .attr("fill", "#666");
        }
      });

    return transition.end();
  }

  function calculateBarWidth(x, d) {
    const widthValue = x(d.totalPitches) - x(0);
    return isNaN(widthValue) ? 0 : widthValue;
  }

  function keyframes(frames) {
    return frames.map(({ date, locationsData }) => {
      const rankedDataArray = rank(locationsData, topCount);
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
    invisibleText.style.font = "12px sans-serif";

    let maxWidth = 0;
    textArray.forEach((text) => {
      invisibleText.textContent = text;
      document.body.appendChild(invisibleText);
      const width = invisibleText.getBoundingClientRect().width;
      maxWidth = Math.max(maxWidth, width);
      document.body.removeChild(invisibleText);
    });

    return maxWidth;
  }

  function ticker(svg, containerWidth, effectiveHeight, y) {
    svg
      .append("text")
      .attr("class", "date-label")
      .attr("x", containerWidth - MARGIN.right)
      .attr("y", effectiveHeight - 10)
      .attr("text-anchor", "end")
      .style("font", `bold ${y.bandwidth()}px var(--sans-serif)`)
      .style("font-variant-numeric", "tabular-nums")
      .attr("fill", "#666");
  }

  location(userTicksData, targetId);
}
