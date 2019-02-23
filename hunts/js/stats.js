import '../scss/stats.scss';

import $ from 'jquery';
import * as d3 from "d3";

// Keep the number of entries in here such that it has a large least common multiple with the number of colours.
var symbolsPathList = [
	{path: "M -3,-3 L 3,3 M 3,-3 L -3,3", strokeWidth: 2, fillOpacity: 0}, // X
	{path: "M -3,0 A 3,3 0 1 1 -3,0.0000001Z", strokeWidth: 0, fillOpacity: 1}, // Filled circle
	{path: "M 0,3 L 3,0 L 0,-3 L -3,0Z", strokeWidth: 0, fillOpacity: 1}, // Filled diamond
	{path: "M 0,-4 L 3.4641016,2 L -3.4641016,2Z", strokeWidth: 0, fillOpacity: 1}, // Filled triangle. I used legit trigonometry to get these coordinates.
	{path: "M -3,-3 L -3,3 L 3,3 L 3,-3Z", strokeWidth: 0, fillOpacity: 1}, // Filled square
	{path: "M 0,4 L 3.4641016,-2 L -3.4641016,-2Z", strokeWidth: 0, fillOpacity: 1}, // Filled upside-down triangle
	{path: "M 0,3 L 0,-3 M -3,0 L 3,0", strokeWidth: 2, fillOpacity: 0}, // +
	{path: "M 0,3 L 3,0 L 0,-3 L -3,0Z", strokeWidth: 2, fillOpacity: 0}, // Diamond
	{path: "M 0,-4 L 3.4641016,2 L -3.4641016,2Z", strokeWidth: 2, fillOpacity: 0}, // triangle
	{path: "M -3,-3 L -3,3 L 3,3 L 3,-3Z", strokeWidth: 2, fillOpacity: 0}, // Square
	{path: "M -3,0 A 3,3 0 1 1 -3,0.0000001Z", strokeWidth: 2, fillOpacity: 0}, // O
];

var hiddenOpacity = 0.1;

// Fuck JS and its lack of a standard library
var entityMap = {
	'&': '&amp;',
	'<': '&lt;',
	'>': '&gt;',
	'"': '&quot;',
	"'": '&#39;',
	'/': '&#x2F;',
	'`': '&#x60;',
	'=': '&#x3D;',
	' ': '&nbsp;'
};

var globalData = null;
var timeout = null;
var invisteams = [];

function escapeHtml (string) {
	"use strict";
	return String(string).replace(/[&<>"'`=\/ ]/g, function (s) {
		return entityMap[s];
	});
}

function getStats(force) {
	"use strict";
	if (timeout) {
		clearTimeout(timeout);
	}
	if (!(force || $('#auto-update').prop('checked'))) {
		return;
	}
	$.get('stats_content/' + $('#episode').val(), {}, function (data) {
		// Get new stats 5 seconds after we got last stats
		timeout = setTimeout(getStats, 5000);
		globalData = data;
		drawGraph();
		restoreView(invisteams);
	});
}

function drawGraph() {
	"use strict";
	clearChart();
	drawFunction(globalData);
}

function drawCompletion(data) {
	"use strict";
	// Create scales for a bar chart
	var x = d3.scaleBand()
		.rangeRound([0, width]).padding(0.1)
		.domain(data.puzzles);
	var y = d3.scaleLinear()
		.domain([0, data.numTeams])
		.range([height, 0]);

	// Join data to a group with class bar
	var bar = chart.selectAll("g.bar")
		.data(data.puzzleCompletion);

	// For new bars, create the group, rectangle and some text
	var enterBar = bar.enter()
		.append("g")
		.attr("class", "bar");
	enterBar.append("rect");
	enterBar.append("text");

	// Update the rectangle...
	var updateBar = enterBar.merge(bar);
	updateBar.attr("transform", function(d, i) { return "translate(" + x(d.puzzle) + ",0)"; })
		.select("rect")
		.attr("y", function(d) { return y(d.completion); })
		.attr("height", function(d) { return height - y(d.completion); })
		.attr("width", x.bandwidth());

	// ...and the text
	var percentFormatter = function (d) { return d3.format(".0%")(d / data.numTeams); };

	updateBar.select("text")
		.attr("y", function(d) { return y(d.completion) + 3; })
		.attr("x", x.bandwidth() / 2)
		.attr("dy", ".75em")
		.text(function (d) { return d.completion; });

	// Clear old bars
	bar.exit().remove();

	// Draw axes and horizontal marker lines
	xAxisElt.call(d3.axisBottom(x))
		.attr("transform", "translate(0," + height + ")")
		.selectAll("text")
		.attr("transform", "rotate(-20)");

	// On the y axis, don't draw the actual numbers but instead a percentage.
	var yForAxis = d3.scaleLinear()
		.domain([0, 1])
		.range([height, 0]);
	var yAxis = d3.axisLeft(yForAxis)
		.tickSize(-width)
		.tickPadding(10)
		.tickFormat(d3.format(".0%"));

	yAxisElt.call(yAxis);
}

function drawTimeCompleted(lines) {
	"use strict";
	return function(data) {
		// Create the X and Y scales
		var x = d3.scalePoint()
			.range([0, width])
			.padding(0.5)
			.domain(data.puzzles);
		var y = d3.scaleTime()
			.domain([new Date(data.startTime), new Date(data.endTime)])
			.range([0, height]);

		// Create scales for the marks on the graph
		var colours = d3.scaleOrdinal(d3.schemeCategory20)
			.domain(data.teams);
		var symbolsList = d3.symbols;
		var symbols = d3.scaleOrdinal()
			.range(symbolsPathList)
			.domain(data.teams);

		var timeCompleted = data.puzzleCompletion.map(
			function (d) { return d.completion; }
		);
		// Load data into team groups
		var team = chart.selectAll("g.team")
			.data(data.puzzleProgress);

		// Kill the paths in the updating groups
		team.selectAll("path").remove();

		// Create new groups
		var enterTeam = team.enter()
			.append("g")
			.attr("class", "team");

		var updateTeam = enterTeam.merge(team);
		team.exit().remove();

		// MAIN STUFF
		// Now add data to this column for each correct answer, create a new path,
		// transform it to the right time and draw a symbol corresponding to the team that made the answer
		updateTeam.selectAll("path")
			.data(function(d, i) { return d.progress; })
			.enter()
			.append("path")
			.attr("transform", function(d, i) { return "translate(" + x(d.puzzle) + "," + y(new Date(d.time)) + ")"; })
			.attr("class", function(d, i) { return "marker hide-team team-" + escapeHtml(parentData(this).team); })
			.attr("fill", function(d) { return colours(parentData(this).team); })
			.attr("fill-opacity", function(d) { return symbols(parentData(this).team).fillOpacity; })
			.attr("stroke", function(d) { return colours(parentData(this).team); })
			.attr("stroke-width", function(d) { return symbols(parentData(this).team).strokeWidth; })
			.attr("d", function(d) { return symbols(parentData(this).team).path; } );

		if (lines) {
			chart.selectAll(".progress-line").remove();
			var progressLine = d3.line()
				.x(function (d) { return x(d.puzzle); })
				.y(function (d) { return y(new Date(d.time)); });
			var inverseScale = d3.scaleQuantize()
				.range(x.domain())
				.domain(x.range());

			data.puzzleProgress.forEach(function (d, i) {
				chart.append("path")
					.attr("class", "line progress-line hide-team team-" + escapeHtml(d.team))
					.attr("stroke", colours(d.team))
					.attr("d", progressLine(d.progress));
				chart.append("path")
					.attr("class", "hover-line team-" + escapeHtml(d.team))
					.attr("stroke", "black")
					.attr("stroke-opacity", 0)
					.attr("fill", "none")
					.attr("stroke-width", 8)
					.attr("d", progressLine(d.progress))
					.on("mouseover", function () { hoverTeam(d, inverseScale, symbols, true); })
					.on("mousemove", function () { hoverTeam(d, inverseScale, symbols, false); })
					.on("mouseout", function () { unhoverTeam(d, symbols); });
			});
		}

		// Draw the axes with large negative tick sizes to get grid lines
		var xAxis = d3.axisTop(x)
			.tickSize(-height)
			.tickPadding(10);
		xAxisElt.call(xAxis)
			.selectAll("text")
			.attr("transform", "rotate(20)");

		var yAxis = d3.axisLeft(y)
			.tickSize(-width)
			.tickPadding(10);
		yAxisElt.call(yAxis);

		drawLegend(data, colours, symbols);
	};
}

function timeFormatter(date) {
	"use strict";
	// When we create dates from the number of seconds, JS interprets them in the local time
	// which makes the display weird. Correct for that here.
	//var seconds = date.getTime() / 1000 - date.getTimezoneOffset()*60;
	var seconds = date;
	return Math.floor(seconds / 3600) + ":" + d3.format("02")(Math.floor(seconds / 60) % 60);
}

function drawTeamPuzzleStuckness(data) {
	"use strict";
	var x = d3.scalePoint()
		.range([0, width])
		.padding(0.5)
		.domain(data.puzzles);
	var maxSeconds = d3.max(data.teamPuzzleStuckness.map(function (d) {
		return d3.max(d.puzzleStuckness.map(function (d) { return d.stuckness; }));
	}));
	var y = d3.scaleTime()
		.domain([0, maxSeconds*1.05])
		.range([height, 0]);

	// Create scales for the marks on the graph
	var colours = d3.scaleOrdinal(d3.schemeCategory20)
		.domain(data.teams);
	var symbolsList = d3.symbols;
	var symbols = d3.scaleOrdinal()
		.range(symbolsPathList)
		.domain(data.teams);

	// Load data into team groups
	var team = chart.selectAll("g.team")
		.data(data.teamPuzzleStuckness);

	// Kill the paths in the updating groups
	team.selectAll("path").remove();

	// Create new groups
	var enterTeam = team.enter()
		.append("g")
		.attr("class", "team");

	var updateTeam = enterTeam.merge(team);
	team.exit().remove();

	// MAIN STUFF
	updateTeam.selectAll("path")
		.data(function(d, i) { return d.puzzleStuckness; })
		.enter()
		.append("path")
		.attr("transform", function(d, i) { return "translate(" + x(d.puzzle) + "," + y(d.stuckness) + ")"; })
		.attr("class", function(d, i) { return "marker hide-team team-" + escapeHtml(parentData(this).team); })
		.attr("fill", function(d) { return colours(parentData(this).team); })
		.attr("fill-opacity", function(d) { return symbols(parentData(this).team).fillOpacity; })
		.attr("stroke", function(d) { return colours(parentData(this).team); })
		.attr("stroke-width", function(d) { return symbols(parentData(this).team).strokeWidth; })
		.attr("d", function(d) { return symbols(parentData(this).team).path; } );

	var xAxis = d3.axisTop(x)
		.tickSize(-height)
		.tickPadding(10);
	xAxisElt.call(xAxis)
		.selectAll("text")
		.attr("transform", "rotate(20)");

	var yAxis = d3.axisLeft(y)
		.tickSize(-width)
		.tickPadding(10)
		.tickFormat(timeFormatter);
	yAxisElt.call(yAxis);

	drawLegend(data, colours, symbols);
}

function drawTeamStuckness(data) {
	"use strict";
	var stuckness = data.teamTotalStuckness.sort(function (a, b) { return b.stuckness - a.stuckness; });
	var y = d3.scaleBand()
		.domain(stuckness.map(function(d) { return d.team; }))
		.range([0, height])
		.padding(0.1);
	var x = d3.scaleTime()
		.domain([0, d3.max(stuckness.map(function(d) { return d.stuckness; }))])
		.range([0, width]);

	var bar = chart.selectAll("g.bar")
		.data(data.teamTotalStuckness);

	var enterBar = bar.enter()
		.append("g")
		.attr("class", "bar");
	enterBar.append("rect");

	var updateBar = enterBar.merge(bar);
	updateBar.attr("transform", function(d, i) { return "translate(0," + y(d.team) + ")"; })
		.select("rect")
		.attr("width", function(d) { return x(d.stuckness); })
		.attr("height", y.bandwidth());

	var xAxis = d3.axisTop(x)
		.tickSize(-height)
		.tickPadding(10)
		.tickFormat(timeFormatter);

	xAxisElt.call(xAxis)
		.selectAll("text")
		.style("text-anchor", "middle");

	yAxisElt.call(d3.axisLeft(y))
		.selectAll("text");
}

function puzzleTimeDrawer(mainPropName, subPropName) {
	"use strict";
	return function (data) {
		// Create scales for a bar chart
		var x = d3.scaleBand()
			.rangeRound([0, width]).padding(0.1)
			.domain(data.puzzles);
		var y = d3.scaleLinear()
			.domain([0, d3.max(data[mainPropName].map(function(d) { return d[subPropName]; }))])
			.range([height, 0]);

		// Join data to a group with class bar
		var bar = chart.selectAll("g.bar")
			.data(data[mainPropName]);

		// For new bars, create the group and rectangle
		var enterBar = bar.enter()
			.append("g")
			.attr("class", "bar");
		enterBar.append("rect");

		// Update the rectangle...
		var updateBar = enterBar.merge(bar);
		updateBar.attr("transform", function(d, i) { return "translate(" + x(d.puzzle) + ",0)"; })
			.select("rect")
			.attr("y", function(d) { return y(d[subPropName]); })
			.attr("height", function(d) { return height - y(d[subPropName]); })
			.attr("width", x.bandwidth());

		// Clear old bars
		bar.exit().remove();

		// Draw axes and horizontal marker lines
		xAxisElt.call(d3.axisBottom(x))
			.attr("transform", "translate(0," + height + ")")
			.selectAll("text")
			.attr("transform", "rotate(-20)");

		var yAxis = d3.axisLeft(y)
			.tickSize(-width)
			.tickPadding(10)
			.tickFormat(timeFormatter);

		yAxisElt.call(yAxis);
	};
}

function teamClass(d) {
	"use strict";
	return '[class~="team-' + escapeHtml(d.team) + '"]';
}

function hoverTeam(data, computePuzzle, symbols, highlight) {
	"use strict";
	var puzzle = computePuzzle(d3.mouse(chart.node())[0]);
	var progress = data.progress.find(function(d) { return d.puzzle == puzzle; });
	if (progress === undefined) return;

	if (highlight) {
		highlightTeam(data, symbols);
	}
	moveTooltip();
	var time = d3.timeFormat("%a %H:%M:%S")(new Date(progress.time));
	drawTooltip([data.team, progress.puzzle + ": " + time]);
	chart.select(".chart-tooltip")
		.style("visibility", "visible");
}

function moveTooltip() {
	"use strict";
	var mouse = d3.mouse(chart.select(".chart-background").node());
	var ttx = mouse[0] + 24,
		tty = mouse[1];
	chart.select(".chart-tooltip")
		.attr("transform", "translate(" + ttx + "," + tty + ")");
}

function drawTooltip(textArray) {
	"use strict";
	var tooltip = chart.select(".chart-tooltip");
	tooltip.selectAll("*").remove();
	var text = tooltip.append("g");

	var lineHeight = 16;
	textArray.forEach(function (d, i) {
		text.append("text")
			.attr("dy", i*lineHeight)
			.text(d);
	});

	var bbox = text.node().getBBox();
	var margin = 6;

	tooltip.append("rect")
		.attr("width", bbox.width + 2 * margin)
		.attr("height", bbox.height + 2 * margin)
		.attr("x", -margin)
		.attr("y", -margin)
		.attr("rx", 6)
		.attr("ry", 6);
	text.raise();
	tooltip.raise();
}

function unhoverTeam(d, symbols) {
	"use strict";
	unhighlightTeam(d, symbols);
	chart.select(".chart-tooltip")
		.style("visibility", "hidden")
		.lower();
}

function highlightTeam(d, symbols) {
	"use strict";
	// Increase the size of the team's lines and markers and raise them
	d3.selectAll(teamClass(d)).filter(".marker")
		.attr("stroke-width", symbols(d.team).strokeWidth + 2)
		.each(function (d) { this.parentNode.parentNode.appendChild(this.parentNode); });
	d3.selectAll(teamClass(d)).filter(".line")
		.style("stroke-width", 3)
		.raise();
	// Also do this for the invisible line to add a bit of hysteresis
	d3.selectAll(teamClass(d)).filter(".hover-line")
		.style("stroke-width", 12)
		.raise();
}

function unhighlightTeam(d, symbols) {
	"use strict";
	d3.selectAll(teamClass(d)).filter(".line")
		.style("stroke-width", null);
	d3.selectAll(teamClass(d)).filter(".marker")
		.attr("stroke-width", symbols(d.team).strokeWidth);
	d3.selectAll(teamClass(d)).filter(".hover-line")
		.style("stroke-width", null);
}

function drawLegend(data, colours, symbols) {
	"use strict";
	// Compute margin from the main graph margin
	var legendMargin = {top: margin.top + 20, right: 0, bottom: 0, left: 6};
	var entryHeight = 16;
	// Add data about the teams
	var legend = d3.select("#legend").selectAll("li").data(data.puzzleProgress);
	legend.selectAll("*").remove();
	var enterLegend = legend.enter()
		.append("li");
	// Transform each group to a position just right of the main graph, and down some for each line
	var updateLegend = enterLegend.merge(legend);
	// Hide/show graph stuff
	updateLegend.on("click", function(d, i) {
		if (d3.event.ctrlKey) {
			var currentlyinvis = d3.select('[class~="invis"]' + teamClass(d)).empty();
			if (currentlyinvis) {
				i = invisteams.indexOf(d.team);
				if (i > -1) {
					invisteams.splice(i, 1);
				}
			} else {
				invisteams.push(d.team);
			}
			d3.selectAll(teamClass(d))
				.classed("invis", currentlyinvis)
				.transition(200)
				.style("opacity", currentlyinvis ? hiddenOpacity : 1);
		} else {
			// If all others are invis and this isn't, unhide all. Otherwise hide all but this one.
			var unhideAll = d3.selectAll('.hide-team:not([class~="invis"]):not(' + teamClass(d) + ')').empty();
			if (unhideAll) {
				invisteams = [];
				d3.selectAll(".hide-team")
					.classed("invis", false)
					.transition(200)
					.style("opacity", 1);
			} else {
				// The second transition overrides the first, so only the second selection has to be complicated
				invisteams = [d.team];
				d3.selectAll(".hide-team")
					.classed("invis", true)
					.transition(200)
					.style("opacity", hiddenOpacity);
				d3.selectAll(teamClass(d))
					.classed("invis", false)
					.transition(200)
					.style("opacity", 1);
			}
		}
	});
	updateLegend.on("mouseover", function(d) { highlightTeam(d, symbols); });
	updateLegend.on("mouseout", function(d) { unhighlightTeam(d, symbols); });
	// Add the team's name
	updateLegend.append("span").text(function(d) { return d.team; });
	// Add the symbol corresponding to that team
	updateLegend.append("svg")
		.attr("class", "li-marker")
		.append("path")
		.attr("transform", "translate(10, 10)")
		.attr("class", function(d, i) { return "marker hide-team team-" + escapeHtml(d.team); })
		.attr("fill", function(d) { return colours(d.team); })
		.attr("fill-opacity", function(d) { return symbols(d.team).fillOpacity; })
		.attr("stroke", function(d) { return colours(d.team); })
		.attr("stroke-width", function(d) { return symbols(d.team).strokeWidth; })
		.attr("d", function(d) { return symbols(d.team).path; });
	// Delete vanished teams
	legend.exit().remove();
}

function parentData(n) {
	"use strict";
	return n.parentNode.__data__;
}

var chart,
	margin,
	width,
	height,
	xAxisElt,
	yAxisElt;

function clearChart() {
	"use strict";
	var svg = d3.select('#episode-stats');
	margin = {top: 100, right: 12, bottom: 100, left: 100};
	width = +svg.attr("width") - margin.left - margin.right;
	height = +svg.attr("height") - margin.top - margin.bottom;

	if (chart) {
		chart.selectAll("*").remove();
	} else {
		svg.append("g")
			.attr("transform", "translate(" + margin.left + "," + margin.top + ")");
	}
	if (!d3.select('#legend').empty()) {
		clearLegend();
	}

	chart = svg.select("g");
	chart.append("rect")
		.attr("width", width)
		.attr("height", height)
		.attr("class", "chart-background");
	chart.append("g")
		.attr("class", "chart-tooltip");

	xAxisElt = chart.append("g")
		.attr("class", "axis axis-x");

	yAxisElt = chart.append("g")
		.attr("class", "axis axis-y");
}

function clearLegend() {
	"use strict";
	d3.selectAll("#legend *").remove();
}

function episodeChanged(ev) {
	"use strict";
	getStats(true);
}

function typeChanged(ev) {
	"use strict";
	var graphType = $('#type').val();
	drawFunction = {
		"percent-complete": drawCompletion,
		"time-completed": drawTimeCompleted(false),
		"progress": drawTimeCompleted(true),
		"team-total-stuckness": drawTeamStuckness,
		"team-puzzle-stuckness": drawTeamPuzzleStuckness,
		"puzzle-stuckness": puzzleTimeDrawer('puzzleAverageStuckness', 'stuckness'),
		"puzzle-difficulty": puzzleTimeDrawer('puzzleDifficulty', 'average_time'),
	}[graphType];
	if (globalData) {
		drawGraph();
	}
}

function restoreView(invisteams) {
	"use strict";
	var nteams = invisteams.length;
	for (var i=0; i<nteams; i++) {
		var team = invisteams[i];
		var teamclass = '.team-' + escapeHtml(team);
		d3.selectAll(teamclass)
			.classed("invis", invisteams)
			.style("opacity", invisteams ? hiddenOpacity : 1);
	}
}



var drawFunction = drawCompletion;

$(function () {
	"use strict";
	$.get('episode_list', {}, function (episodes) {
		var select = $('#episode');
		select.children(':not([value="all"])').remove();
		episodes.forEach(function (d) {
			select.append('<option value="' + d.id + '">' + escapeHtml(d.name) + '</option>');
		});
		select.change(episodeChanged);
	});
	clearChart();
	typeChanged();
	getStats(true);
	$('#type').change(typeChanged);
	$('#auto-update').click(function (ev) {
		if ($(this).prop('checked')) {
			getStats();
		}
	});
});

