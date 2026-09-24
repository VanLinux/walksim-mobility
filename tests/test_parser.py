from walksim.sumo.parser import parse_personinfo


def test_parser_aggregates_person_walks(tmp_path) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <personinfos>
      <personinfo id="AB.0" depart="0.00">
        <walk depart="0.00" arrival="80.00" duration="80.00"
              routeLength="100.00" timeLoss="5.00" />
      </personinfo>
      <personinfo id="BA.0" depart="1.00">
        <walk depart="1.00" arrival="101.00" duration="100.00"
              routeLength="100.00" timeLoss="8.00" />
      </personinfo>
    </personinfos>
    """
    path = tmp_path / "personinfo.xml"
    path.write_text(xml, encoding="utf-8")

    result = parse_personinfo(path)

    assert result.total.completed_walks == 2
    assert result.ab.completed_walks == 1
    assert result.ba.completed_walks == 1
    assert result.ab.mean_speed_mps == 1.25
    assert result.ba.mean_speed_mps == 1.0
