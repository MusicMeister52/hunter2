import {
  Chart,
  LineElement,
  PointElement,
  LineController,
  CategoryScale,
  LinearScale,
  TimeScale,
  Legend,
} from 'chart.js'
import 'chartjs-adapter-luxon'
import distinctColors from 'distinct-colors'

Chart.register(
  LineElement,
  PointElement,
  LineController,
  CategoryScale,
  LinearScale,
  TimeScale,
  Legend,
)

let dateAxis = 'x'
let puzzleAxis = 'y'
let puz0name = '(started)'

function generateTeamColours(episode_progress) {
  let team_set = new Set()
  for (let episode in episode_progress) {
    for (let team of episode_progress[episode].teams) {
      team_set.add(team.team_id)
    }
  }
  let colours = distinctColors({count: team_set.size, chromaMin: 10, chromaMax: 90, lightMin: 20, lightMax: 80})
  let teams = Array.from(team_set)
  let team_colours = new Map()
  for (let i = 0; i < teams.length; ++i) {
    team_colours.set(teams[i], colours[i])
  }
  return team_colours
}

function timesToChartForm(data, puzfn) {
  let times = data.puzzle_times
  let result = []
  for (let i = 0; i < times.length; ++i)
    result.push({[puzzleAxis]: puzfn(i), [dateAxis]: times[i].date})
  return result
}

function getChartDataSets(teamData, team_colours) {
  let puzFn = function (n) {
    return n
  }
  if (Object.prototype.hasOwnProperty.call(teamData, 'puzzle_names')) {
    puzFn = function(n) {
      return (n > 0) ? teamData.puzzle_names[n-1] : puz0name
    }
  }

  let teamChartDatasets = []
  for (let team of teamData.teams) {
    let colour = team_colours.get(team.team_id).css()
    teamChartDatasets.push({
      data: timesToChartForm(team, puzFn),
      backgroundColor: colour,
      borderColor: colour,
      borderWidth: 2,
      hoverBorderColor: colour,
      hoverBorderWidth: 4,
      fill: false,
      label: team.team_name,
      lineTension: 0,
      pointRadius: 2,
      pointHoverRadius: 2,
    })
  }
  return teamChartDatasets
}

function setAllHidden(chart, hidden) {
  chart.data.datasets.forEach(dataset => {
    dataset.hidden = hidden
  })
  chart.update()
}

let team_colours = generateTeamColours(window.episode_progress)

for (let canvas of document.getElementsByClassName('progress-graph')) {
  let puzAxis = {}

  let episode_data = window.episode_progress[canvas.dataset.episode]

  if (Object.prototype.hasOwnProperty.call(episode_data, 'puzzle_names')) {
    puzAxis.type = 'category'
    puzAxis.labels = [puz0name].concat(episode_data.puzzle_names).reverse()
  } else {
    puzAxis.type = 'linear'
    puzAxis.ticks = {
      stepSize: 1,
      suggestedMin: 0,
      precision: 0,
      beginAtZero: true,
    }
  }

  let teamChartDatasets = getChartDataSets(episode_data, team_colours)

  let height = 0.2 * window.innerHeight
  canvas.height = height
  canvas.style.height = height
  let ctx = canvas.getContext('2d')
  let chart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: teamChartDatasets,
    },
    options: {
      hover: {
        mode: 'dataset',
      },
      layout: {
        padding: {
          left: 50,
          right: 50,
          top: 50,
          bottom: 50,
        },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'hour',
            displayFormats: {hour: 'HH:mm'},
          },
        },
        y: puzAxis,
      },
    },
  })

  let showAllButton = document.getElementById(`show-all-${canvas.dataset.episode}`)
  showAllButton.addEventListener('click', function() {
    setAllHidden(chart, false)
  })

  let hideAllButton = document.getElementById(`hide-all-${canvas.dataset.episode}`)
  hideAllButton.addEventListener('click', function() {
    setAllHidden(chart, true)
  })
}
