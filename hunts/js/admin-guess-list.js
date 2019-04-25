import $ from 'jquery'
import BPagination from 'bootstrap-vue/es/components/pagination/pagination'
import BTable from 'bootstrap-vue/es/components/table/table'
import URI from 'urijs'
import moment from 'moment'

export default {
  components: {
    'b-pagination': BPagination,
    'b-table': BTable,
  },
  created: function() {
    this.updateData(true)
  },
  data: function() {
    let search = URI(window.location).search(true)
    let page = 'page' in search ? search.page : 1
    delete search.page
    return {
      autoUpdate: true,
      currentPage: page,
      fields: [
        'episode',
        'puzzle',
        'user',
        'seat',
        'guess',
        'given',
        'time_on_puzzle',
      ],
      filter: search,
      guesses: [],
      highlightUnlocks: false,
      rows: 0,
    }
  },
  filters: {
    moment: function(time, format) {
      return moment(time).format(format)
    },
  },
  methods: {
    changePage: function(page) {
      this.autoUpdate = page === 1
      this.currentPage = page
      let new_uri = URI(window.location)
      if (page == 1) {
        new_uri.removeSearch('page')
      } else {
        new_uri.setSearch('page', page)
      }
      window.history.pushState('', '', new_uri)
      this.updateData(true)
    },
    addFilter: function(type, value) {
      this.filter[type] = value
      this.currentPage = 1
      let new_uri = URI(window.location).setSearch(type, value).removeSearch('page')
      window.history.pushState('', '', new_uri)
      this.updateData(true)
    },
    clearFilters: function() {
      this.autoUpdate = true
      this.currentPage = 1
      this.filter = {}
      let new_uri = URI(window.location).search({})
      window.history.pushState('', '', new_uri)
      this.updateData(true)
    },
    updateData: function(force) {
      clearTimeout(this.timer)
      let page = this.currentPage
      if (force || this.autoUpdate) {
        let guesses_url = URI(this.href).search({...this.filter, 'highlight_unlocks': this.highlightUnlocks, 'page': page})
        let v = this
        $.get(guesses_url).done(function(data) {
          for (let guess of data.guesses) {
            if (guess.correct) {
              guess._rowVariant = 'success'
              continue
            }
            if (guess.unlocked) {
              guess._rowVariant = 'info'
              continue
            }
          }
          v.guesses = data.guesses
          v.rows = data.rows
        })
        if (this.autoUpdate) {
          this.timer = setTimeout(this.updateData, 5000)
        }
      }
    },
  },
  props: {
    href: {
      type: String,
      required: true,
    },
    perPage: {
      default: 50,
      type: Number,
    },
  },
  watch: {
    autoUpdate: function(on) {
      if (on) {
        this.updateData()
      }
    },
    highlightUnlocks: function() {
      this.updateData(true)
    },
  },
}
