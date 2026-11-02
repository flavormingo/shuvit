import XCTest

final class MapFlowTests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launch()
    }

    private var searchField: XCUIElement {
        app.textFields["Find a park or place"]
    }

    private func search(_ query: String) {
        XCTAssertTrue(searchField.waitForExistence(timeout: 20))
        searchField.tap()
        searchField.typeText(query + "\n")
        XCTAssertTrue(app.staticTexts["PARKS"].waitForExistence(timeout: 20) || app.staticTexts["PLACES"].exists)
    }

    func testSearchFindsParkAndOpensItsCard() {
        search("Burnside")
        let result = app.staticTexts["Burnside Skatepark"]
        XCTAssertTrue(result.waitForExistence(timeout: 10))
        result.tap()
        XCTAssertTrue(app.buttons["Details"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts["PARKS"].exists)
    }

    func testDetailsOpenFromSearchResult() {
        search("Burnside")
        app.staticTexts["Burnside Skatepark"].tap()
        let details = app.buttons["Details"]
        XCTAssertTrue(details.waitForExistence(timeout: 10))
        details.tap()
        XCTAssertTrue(app.buttons["Add Photo"].waitForExistence(timeout: 15))
    }

    func testSearchFindsPlaces() {
        search("Paris")
        XCTAssertTrue(app.staticTexts["PLACES"].waitForExistence(timeout: 15))
        app.staticTexts["PLACES"].firstMatch.swipeUp()
    }

    func testClusterTapZoomsIn() {
        search("Paris")
        let place = app.scrollViews["search-results"].buttons.firstMatch
        XCTAssertTrue(place.waitForExistence(timeout: 10))
        place.tap()

        let cluster = app.buttons["park-cluster"].firstMatch
        guard cluster.waitForExistence(timeout: 20) else {
            XCTFail("No clusters on the map over Paris")
            return
        }
        let before = app.buttons.matching(identifier: "park-cluster").count
        cluster.tap()
        sleep(4)
        let pinsAfter = app.otherElements.matching(identifier: "park-pin").count
            + app.buttons.matching(identifier: "park-pin").count
        let clustersAfter = app.buttons.matching(identifier: "park-cluster").count
        XCTAssertTrue(pinsAfter > 0 || clustersAfter != before)
    }

    func testFiltersChangeWhatTheMapShows() {
        let filterButton = app.buttons["filter-toggle"]
        XCTAssertTrue(filterButton.waitForExistence(timeout: 20))
        filterButton.tap()
        XCTAssertTrue(app.buttons["Indoor"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.staticTexts["TYPE"].exists)
        app.buttons["Indoor"].tap()
        XCTAssertTrue(app.buttons["Clear all"].waitForExistence(timeout: 5))
    }
}
