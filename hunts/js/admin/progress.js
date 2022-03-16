import 'bootstrap/js/dist/button'
import 'bootstrap/js/dist/collapse'
import ProgressState from './state.vue'
import {DateTime, Duration} from 'luxon'

export default {
  components: {
    'progress-state': ProgressState,
  },
  computed: {
    episodes: function () {
      return this.puzzles.map(puzzle => {
        return puzzle.episode
      }).filter((v, i, a) => a.indexOf(v) === i)
    },
    fields: function () {
      // Prepend an entry for the team name
      return this.puzzles.filter(pz => {
        // Filter out entries for puzzles from unselected episodes
        return this.displayForEpisodeNum(pz.episode)
      }).map(pz => {return {
        label: pz.short_name,
        headerTitle: pz.title,
      }})
    },
    progress_data: function () {
      return this.team_progress.map(team => {
        // Step 1: Filter out *puzzles* which are not from selected episodes
        return {name: team.name, url: team.url, progress: team.progress.filter(puzzle_progress => {
          return this.displayForEpisodeNum(puzzle_progress.episode_number)
        })}
      }).filter(team => {
        // Step 2: Apply filters to each team's row
        let open_puzzles = team.progress.filter(puzzle_progress => {
          return (
            puzzle_progress.state === 'open'
            && (!puzzle_progress.hints_scheduled || !this.filters.no_hints)
          )
        }).length
        let latest_guess = Math.min(...team.progress.filter(
          puzzle_progress => puzzle_progress.latest_guess !== null,
        ).map(
          puzzle_progress => -DateTime.fromISO(puzzle_progress.latest_guess).diffNow().as('milliseconds'),
        ))
        let total_guesses = team.progress.map(
          puzzle_progress => puzzle_progress.guesses,
        ).filter(
          guesses => guesses !== null,
        ).reduce((a, b) => a + b, 0)
        return (
          open_puzzles >= this.filters.open_puzzles[0] &&
          open_puzzles <= this.filters.open_puzzles[1] &&
          latest_guess >= this.filters.latest_guess[0] * 60 * 1000 &&
          (
            // If the user wants to filter out puzzles with no guesses that's separate
            latest_guess === Infinity ||
            latest_guess <= this.filters.latest_guess[1] * 60 * 1000
          ) &&
          total_guesses >= this.filters.total_guesses[0] &&
          total_guesses <= this.filters.total_guesses[1]
        )
      })
    },
    oldest_latest_guess: function() {
      if (this.puzzles.length === 0) {
        return Infinity
      }
      return Math.max(
        ...this.team_progress.map(team => {
          let val = Math.max(...team.progress.filter(
            puzzle_progress => puzzle_progress.latest_guess !== null,
          ).map(
            puzzle_progress => -DateTime.fromISO(puzzle_progress.latest_guess).diffNow().as('milliseconds'),
          ))
          if (val === Infinity) return 0
          return val
        }),
      )
    },
    max_total_guesses: function () {
      if (this.puzzles.length === 0) {
        return Infinity
      }
      return Math.max(
        ...this.team_progress.map(team => team.progress.map(
          puzzle_progress => puzzle_progress.guesses,
        ).filter(
          guesses => guesses !== null,
        ).reduce((a, b) => a + b, 0),
        ),
      )
    },
  },
  created: function() {
    this.updateData(true)
  },
  props: ['href'],
  data () {
    return {
      puzzles: [],
      team_progress: [],
      autoUpdate: true,
      filters: {
        episodes: [],
        open_puzzles: [-Infinity, Infinity],
        latest_guess: [-Infinity, Infinity],
        total_guesses: [-Infinity, Infinity],
        no_hints: false,
      },
    }
  },
  methods: {
    now: DateTime.local,
    clearFilters: function() {
      this.filters = {
        episodes: [],
        open_puzzles: [-Infinity, Infinity],
        latest_guess: [-Infinity, Infinity],
        total_guesses: [-Infinity, Infinity],
        no_hints: false,
      }
    },
    hover_info: function(state) {
      if (state.state === 'not_opened') {
        return ''
      }
      let display_format = { year: 'numeric', month: 'short', day: 'numeric', weekday: 'short', hour: 'numeric', minute: 'numeric' }
      let latest = DateTime.fromISO(state.latest_guess).toLocaleString(display_format)
      let latest_str = state.latest_guess === null ? '' : `\nlatest guess: ${latest}`
      let time_on = Duration.fromMillis(state.time_on * 1000).toFormat('hh:mm:ss')
      let time_on_str = state.time_on === null ? '' : `\ntime on: ${time_on}`
      return `guesses: ${state.guesses}` + latest_str + time_on_str
    },
    updateData: function(force) {
      clearTimeout(this.timer)
      if (force || this.autoUpdate) {
        let v = this
        fetch(this.href).then(
          response => response.json(),
        ).then(
          data => {
            let old_puzzle_length = v.puzzles.length
            let old_oldest_latest_guess = v.oldest_latest_guess
            let old_max_total_guesses = v.max_total_guesses
            v.puzzles = data.puzzles
            v.team_progress = data.team_progress

            if (v.filters.open_puzzles[1] === old_puzzle_length)
              v.filters.open_puzzles[1] = v.puzzles.length
            if (v.filters.latest_guess[1] === old_oldest_latest_guess)
              v.filters.latest_guess[1] = v.oldest_latest_guess
            if (v.filters.total_guesses[1] === old_max_total_guesses)
              v.filters.total_guesses[1] = v.max_total_guesses
          },
        )
        if (this.autoUpdate) {
          this.timer = setTimeout(this.updateData, 5000)
        }
      }
    },
    displayForEpisodeNum: function(n) {
      if (this.filters.episodes.length === 0) return true
      if (this.filters.episodes == this.episodes) return true
      return this.filters.episodes.includes(n)
    },
    log(obj) {
      console.log(obj)
    },
  },
  watch: {
    autoUpdate: function (on) {
      if (on) {
        this.updateData()
      }
    },
  },
}
