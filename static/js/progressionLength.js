document.addEventListener("DOMContentLoaded", function() {

  function progressionLengthChart(userTicksData, targetId) {
    // Custom date parsing function
    const parseDate = d3.timeParse('%Y-%m-%d');

    function getColor(category, type) {
      const colors = {
        'length': {
          'short': 'blue',
          'medium': 'green',
          'long': 'orange',
          'multipitch': 'red'
        },
      };

      return colors[type][category] || 'black';
    }

    function prepareData(userTicksData, mapFn) {

      const hasInvalidDates = userTicksData.some((entry) => 
        !entry.tick_date || 
        (typeof entry.tick_date === 'string' && entry.tick_date.trim() === '')
      );
      if (hasInvalidDates) {
        throw new Error('userTicksData contains invalid data or null date values');
      }

      return userTicksData.map(mapFn);
    }
    
    function createChart(inputData, categoryField,categoryType, colorFunc, filterFunc, svgId) {
      const margin = { top: 20, right: 20, bottom: 30, left: 50 };
      const width = 800 - margin.left - margin.right;
      const height = 300 - margin.top - margin.bottom;
    
      const svg = d3
        .select(svgId)
        .append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g')
        .attr('transform', `translate(${margin.left}, ${margin.top})`);
    
      const xScale = d3.scaleTime().range([0, width]);
      const yScale = d3.scaleLinear().range([height, 0]);
    
      const line = d3.line()
        .defined(d => d.category !== null && d.category !== undefined) // Skip the null/undefined values
        .x((d) => xScale(d.date))
        .y((d) => yScale(d.totalPitches));
  
    
      const categories = [...new Set(inputData.map((d) => d[categoryField]))];
      let dataByCategory = {};
    
      categories.forEach((cat) => {
        dataByCategory[cat] = inputData
          .filter((d) => d[categoryField] === cat)
          .sort((a, b) => new Date(a.date) - new Date(b.date));
    
        let totalPitches = 0;
        dataByCategory[cat].forEach((d) => {
          totalPitches += d.pitches;
          d.totalPitches = totalPitches;
        });
      });
      
      const allData = [].concat(...Object.values(dataByCategory));
    
      xScale.domain(d3.extent(allData, (d) => new Date(d.date)));
      yScale.domain([0, d3.max(allData, (d) => d.totalPitches)]);
    
      svg
        .append('g')
        .attr('transform', `translate(0, ${height})`)
        .call(d3.axisBottom(xScale));
    
      svg
        .append('g')
        .call(d3.axisLeft(yScale));
      

      categories.forEach((cat) => {
        svg
          .append('path')
          .datum(dataByCategory[cat])
          .attr('class', 'line')
          .attr('d', line)
          .style('stroke', colorFunc(cat))
          .style('fill', 'none');
      });

      // Define the specific order of categories for the legend
      let orderedCategories;
      if (categoryType.toLowerCase() === 'length') {
        orderedCategories = ['short', 'medium', 'long', 'multipitch'];
      }

      // Add the legend at the end
      const legendSpace = 20;  // Define spacing between legend items
      
      const legend = svg.append('g')
        .attr('class', 'legend')
        .attr('transform', 'translate(5, 5)');  // Position of the whole legend
      
      orderedCategories.forEach((cat, i) => {
        legend.append('rect')
          .attr('x', 0)
          .attr('y', i * legendSpace)
          .attr('width', 10)
          .attr('height', 10)
          .style('fill', colorFunc(cat));
        
        legend.append('text')
          .attr('x', 20)  // Spacing between the rectangle and the text
          .attr('y', i * legendSpace + 9)
          .text(cat)
          .attr('font-size', '12px')
          .attr('alignment-baseline','middle');
      });
    }
    

    d3.select(targetId).select("svg").remove();

    var discipline = d3.select("input[name='length-cat-discipline-filter']:checked").node().value;
    var timeFrame = d3.select("input[name='length-cat-time-filter']:checked").node().value;
    
    // Apply filters
    var filteredData = CommonFilters.filterByDiscipline(userTicksData, discipline);
    filteredData = CommonFilters.filterByTime(filteredData, timeFrame);
    filteredData = prepareData( 
      filteredData,
      (d) => ({ date: parseDate(d.tick_date), category: d.length_category, pitches: d.pitches || 0 }),
    );
    createChart(filteredData, 'category', 'length', (cat) => getColor(cat, 'length'), (d) => true, '#length-cat');
  }
  
  // Add event listeners to your filters
  d3.selectAll("input[name='length-cat-discipline-filter']").on('change', function() {
    progressionLengthChart(userTicksData, '#length-cat');
    });
  
  d3.selectAll("input[name='length-cat-time-filter']").on('change', function(){
    progressionLengthChart(userTicksData, '#length-cat');
    });

  progressionLengthChart(userTicksData, '#length-cat');


});
